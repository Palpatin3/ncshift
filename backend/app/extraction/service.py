"""Orchestration de l'extraction (sprint 2) : extraire, noter, tracer, router.

Toute extraction passe par `extraire_facture` :

  1. choisir l'extracteur compétent pour le type détecté (jamais l'extension) ;
  2. exécuter puis noter : score global + avis machine-lisibles ;
  3. écrire la ligne `extraction` (append-only, comme le journal) et copier
     les champs métier sur la facture (numéro, dates, montants, score) ;
  4. faire vivre la machine à états par `changer_statut` uniquement :
     recue -> extraite ; si le score est sous le seuil, extraite -> a_valider
     (le court-circuit vers l'humain prévu par la machine à états).

Une extraction ratée n'est jamais une exception : c'est un événement tracé.
Le commit appartient à l'appelant, ce service ne fait que des flush.
"""
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..core.audit import changer_statut, journaliser
from ..ingestion.storage import charger
from ..models import Facture, FichierSource, StatutFacture
from ..models.extraction import Extraction
from .base import DonneesFacture, ExtractionErreur, Extracteur
from .facturx import ExtracteurFacturX
from .score import noter

# Le registre des moteurs : l'OCR + LLM Mistral s'ajoutera ici (sprint 2.5)
EXTRACTEURS: list[Extracteur] = [ExtracteurFacturX()]


def peut_extraire(type_fichier: str) -> bool:
    return any(e.peut_extraire(type_fichier) for e in EXTRACTEURS)


def extraire_facture(
    db: Session,
    *,
    facture: Facture,
    fichier: FichierSource,
    contenu: bytes | None = None,
    acteur: str = "extractor",
) -> dict | None:
    """Tente l'extraction d'une facture `recue`. Retourne un résumé, ou
    None si aucun moteur ne sait traiter ce type. Ne lève jamais."""
    moteur = next(
        (e for e in EXTRACTEURS if e.peut_extraire(fichier.type_detecte)), None
    )
    if moteur is None:
        return None

    if contenu is None:
        contenu = _relire_contenu(fichier)

    donnees: DonneesFacture
    try:
        donnees = moteur.extraire(contenu or b"", fichier.type_detecte)
    except ExtractionErreur as e:
        return _echec(db, facture=facture, methode=moteur.nom, raison=e.raison, acteur=acteur)

    score, avis = noter(donnees)

    db.add(
        Extraction(
            organisation_id=facture.organisation_id,
            facture_id=facture.id,
            methode=moteur.nom,
            reussie=True,
            donnees=donnees.vers_json(),
            avis=avis or None,
            score=score,
        )
    )
    _copier_sur_facture(facture, donnees, score)
    journaliser(
        db,
        organisation_id=facture.organisation_id,
        entite_type="facture",
        entite_id=facture.id,
        evenement="extraction",
        acteur=acteur,
        details={
            "methode": moteur.nom,
            "score": score,
            "avis": avis,
            "fichier_source_id": str(fichier.id),
        },
    )
    changer_statut(
        db,
        facture=facture,
        nouveau_statut=StatutFacture.EXTRAITE,
        acteur=acteur,
        details={"methode": moteur.nom, "score": score},
    )
    if score < settings.seuil_confiance:
        journaliser(
            db,
            organisation_id=facture.organisation_id,
            entite_type="facture",
            entite_id=facture.id,
            evenement="score_faible",
            acteur=acteur,
            details={"score": score, "seuil": settings.seuil_confiance, "avis": avis},
        )
        changer_statut(
            db,
            facture=facture,
            nouveau_statut=StatutFacture.A_VALIDER,
            acteur=acteur,
            details={"score": score, "avis": avis},
        )
    return {"reussie": True, "methode": moteur.nom, "score": score, "avis": avis, "statut": facture.statut}


def _relire_contenu(fichier: FichierSource) -> bytes | None:
    try:
        return charger(fichier.s3_key)
    except Exception:
        return None


def _copier_sur_facture(facture: Facture, donnees: DonneesFacture, score: float) -> None:
    from datetime import date as _date

    def _en_date(valeur: str | None) -> _date | None:
        # La colonne est un `Date` : l'ISO de l'extracteur devient un vrai date.
        return _date.fromisoformat(valeur) if valeur else None

    facture.numero = donnees.numero
    facture.date_facture = _en_date(donnees.date_facture)
    facture.date_echeance = _en_date(donnees.date_echeance)
    facture.devise = donnees.devise or "EUR"
    facture.montant_ht = donnees.montant_ht
    facture.montant_ttc = donnees.montant_ttc
    facture.score_confiance = score


def _echec(
    db: Session, *, facture: Facture, methode: str, raison: str, acteur: str
) -> dict:
    db.add(
        Extraction(
            organisation_id=facture.organisation_id,
            facture_id=facture.id,
            methode=methode,
            reussie=False,
            donnees=None,
            avis=[raison],
            score=None,
        )
    )
    journaliser(
        db,
        organisation_id=facture.organisation_id,
        entite_type="facture",
        entite_id=facture.id,
        evenement="extraction_echouee",
        acteur=acteur,
        details={"methode": methode, "raison": raison},
    )
    return {"reussie": False, "methode": methode, "raison": raison, "statut": facture.statut}
