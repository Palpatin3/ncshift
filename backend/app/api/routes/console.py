"""Routes API du sprint 2 : regarder le système, déposer, extraire.

Pas d'auth au sprint 1 (démo locale) ; FastAPI-Users arrive au sprint 4.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import Facture, FichierSource, AuditLog
from ...core.audit import changer_statut
from ...core.org import organisation_defaut
from ...extraction.service import extraire_facture
from ...ingestion.service import enregistrer_fichier, ResultatIngestion
from ...models.enums import StatutFacture

router = APIRouter(prefix="/api")


def _serializer_fichier(f: FichierSource) -> dict:
    return {
        "id": str(f.id),
        "nom_fichier": f.nom_fichier,
        "canal": f.canal,
        "type_detecte": f.type_detecte,
        "sha256": f.sha256,
        "taille_octets": f.taille_octets,
        "recu_le": f.recu_le.isoformat(),
    }


def _serializer_facture(f: Facture, fichier: FichierSource | None) -> dict:
    return {
        "id": str(f.id),
        "statut": f.statut,
        "numero": f.numero,
        "montant_ttc": float(f.montant_ttc) if f.montant_ttc is not None else None,
        "devise": f.devise,
        "score_confiance": f.score_confiance,
        "fichier": _serializer_fichier(fichier) if fichier else None,
    }


@router.get("/fichiers")
def lister_fichiers(db: Session = Depends(get_db)):
    fichiers = db.scalars(select(FichierSource).order_by(FichierSource.recu_le.desc()).limit(100)).all()
    return [_serializer_fichier(f) for f in fichiers]


@router.get("/factures")
def lister_factures(db: Session = Depends(get_db)):
    factures = db.scalars(select(Facture).order_by(Facture.created_at.desc()).limit(100)).all()
    resultat = []
    for f in factures:
        fichier = db.get(FichierSource, f.fichier_source_id)
        resultat.append(_serializer_facture(f, fichier))
    return resultat


@router.get("/factures/{facture_id}")
def detail_facture(facture_id: uuid.UUID, db: Session = Depends(get_db)):
    f = db.get(Facture, facture_id)
    if f is None:
        raise HTTPException(404, "Facture inconnue")
    fichier = db.get(FichierSource, f.fichier_source_id)
    audit = db.scalars(
        select(AuditLog)
        .where(AuditLog.entite_type == "facture", AuditLog.entite_id == f.id)
        .order_by(AuditLog.created_at)
    ).all()
    return {
        **_serializer_facture(f, fichier),
        "audit": [_ligne_audit(a) for a in audit],
    }


@router.post("/factures/{facture_id}/statut")
def changer_statut_facture(
    facture_id: uuid.UUID,
    nouveau_statut: str,
    acteur: str = "demo",
    db: Session = Depends(get_db),
):
    """Endpoint de démo pour faire vivre la machine à états depuis la console."""
    f = db.get(Facture, facture_id)
    if f is None:
        raise HTTPException(404, "Facture inconnue")
    try:
        changer_statut(db, facture=f, nouveau_statut=nouveau_statut, acteur=acteur)
        db.commit()
    except ValueError:
        raise HTTPException(400, f"Statut inconnu : {nouveau_statut}")
    except Exception:
        db.rollback()
        raise HTTPException(
            409,
            f"Transition interdite : {f.statut} -> {nouveau_statut}",
        )
    return {"id": str(f.id), "statut": f.statut}


def _ligne_audit(a: AuditLog) -> dict:
    return {
        "id": str(a.id),
        "entite_type": a.entite_type,
        "entite_id": str(a.entite_id),
        "evenement": a.evenement,
        "ancien_statut": a.ancien_statut,
        "nouveau_statut": a.nouveau_statut,
        "acteur": a.acteur,
        "details": a.details,
        "created_at": a.created_at.isoformat(),
    }


@router.post("/fichiers")
async def televerser_fichier(fichier: UploadFile, db: Session = Depends(get_db)):
    """Démo / secours : simule l'arrivée d'un fichier par n'importe quel canal.
    Utile pour la console quand ni la boîte mail ni le dossier ne sont câblés."""
    org = organisation_defaut(db)
    contenu = await fichier.read()
    resultat: ResultatIngestion = enregistrer_fichier(
        db,
        organisation_id=org.id,
        nom_fichier=fichier.filename or "sans-nom",
        contenu=contenu,
        canal="api",
        acteur="console",
    )
    # Extraction immédiate quand un moteur sait lire ce type : le résultat
    # (score, avis, nouveau statut) remonte à la console sans rechargement.
    # Le worker refait de toute façon le tour des `recue` à la minute +30s :
    # ce qui réussit ici sera simplement déjà passé.
    extraction = None
    if resultat.facture is not None:
        extraction = extraire_facture(
            db,
            facture=resultat.facture,
            fichier=resultat.fichier,
            contenu=contenu,
            acteur="console",
        )
    db.commit()
    return {
        "nouveau": resultat.nouveau,
        "fichier": _serializer_fichier(resultat.fichier),
        "facture_id": str(resultat.facture.id) if resultat.facture else None,
        "extraction": extraction,
    }


@router.get("/journal")
def journal(db: Session = Depends(get_db)):
    lignes = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(50)).all()
    return [_ligne_audit(a) for a in lignes]
