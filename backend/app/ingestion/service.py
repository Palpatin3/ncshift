"""Service d'ingestion : le point d'entrée unique de tout fichier entrant.

Mail, dossier partagé, API plus tard : tout passe par `enregistrer_fichier`,
qui garantit, dans cet ordre :
  1. empreinte SHA-256 et dédoublonnage par (organisation, hash) ;
  2. détection du type par le contenu ;
  3. dépôt du fichier brut (S3 en prod, dossier local en dev) ;
  4. ligne de fichier_source + ligne d'audit `fichier_recu` ;
  5. si le fichier peut être une facture (PDF ou XML), ligne de facture
     dans l'état `recue`, avec sa ligne d'audit.

Le commit appartient à l'appelant : l'ingestion ne fait que des flush.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.audit import journaliser
from ..models import Facture, FichierSource, StatutFacture, TypeFichier
from ..config import settings
from .detect import detecter_type
from .storage import televerser

TYPES_FACTURE = {TypeFichier.PDF.value, TypeFichier.PDF_A3_FACTURX.value, TypeFichier.XML.value}


@dataclass
class ResultatIngestion:
    fichier: FichierSource | None
    facture: Facture | None
    nouveau: bool  # False = doublon ignoré


def empreinte(contenu: bytes) -> str:
    import hashlib

    return hashlib.sha256(contenu).hexdigest()


def _cle_stockage(organisation_id, h: str, nom_fichier: str) -> str:
    base = f"{organisation_id}/{h[:2]}/{h}"
    nom = (nom_fichier or "sans-nom").replace("/", "_")[:180]
    return f"{base}/{nom}"


def enregistrer_fichier(
    db: Session,
    *,
    organisation_id: uuid.UUID,
    nom_fichier: str,
    contenu: bytes,
    canal: str,
    message_id: str | None = None,
    recu_le: datetime | None = None,
    acteur: str = "system",
) -> ResultatIngestion:
    recu_le = recu_le or datetime.now(timezone.utc)
    h = empreinte(contenu)

    existant = db.scalar(
        select(FichierSource)
        .where(
            FichierSource.organisation_id == organisation_id,
            FichierSource.sha256 == h,
        )
        .limit(1)
    )
    if existant is not None:
        # Doublon : on n'ignore jamais silencieusement, on le trace.
        journaliser(
            db,
            organisation_id=organisation_id,
            entite_type="fichier_source",
            entite_id=existant.id,
            evenement="doublon_ignore",
            acteur=acteur,
            details={
                "sha256": h,
                "nom_recu": nom_fichier,
                "canal": canal,
                "fichier_existant_id": str(existant.id),
            },
        )
        return ResultatIngestion(fichier=existant, facture=None, nouveau=False)

    type_detecte = detecter_type(nom_fichier, contenu)

    cle_stockage = None
    if settings.stockage != "off":
        cle_stockage = televerser(contenu, _cle_stockage(organisation_id, h, nom_fichier))

    fichier = FichierSource(
        organisation_id=organisation_id,
        nom_fichier=(nom_fichier or "sans-nom")[:512],
        canal=canal,
        sha256=h,
        type_detecte=type_detecte,
        taille_octets=len(contenu),
        s3_key=cle_stockage,  # colonne historique : adresse de stockage, S3 ou local
        message_id=message_id,
        recu_le=recu_le,
    )
    db.add(fichier)
    db.flush()

    journaliser(
        db,
        organisation_id=organisation_id,
        entite_type="fichier_source",
        entite_id=fichier.id,
        evenement="fichier_recu",
        nouveau_statut=type_detecte,
        acteur=acteur,
        details={
            "canal": canal,
            "type": type_detecte,
            "taille_octets": len(contenu),
            "sha256": h,
            "nom_fichier": fichier.nom_fichier,
            "message_id": message_id,
        },
    )

    facture = None
    if type_detecte in TYPES_FACTURE:
        facture = Facture(
            organisation_id=organisation_id,
            fichier_source_id=fichier.id,
            statut=StatutFacture.RECUE.value,
        )
        db.add(facture)
        db.flush()
        journaliser(
            db,
            organisation_id=organisation_id,
            entite_type="facture",
            entite_id=facture.id,
            evenement="recue",
            nouveau_statut=StatutFacture.RECUE.value,
            acteur=acteur,
            details={"fichier_source_id": str(fichier.id)},
        )

    return ResultatIngestion(fichier=fichier, facture=facture, nouveau=True)
