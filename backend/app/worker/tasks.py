"""Worker arq : poll IMAP périodique + extraction + watcher dossier partagé.

Un seul worker au départ (roadmap : technologies ennuyeuses).
Le poll IMAP tourne chaque minute, l'extraction des factures reçues à
l'heure +30s ; le watcher vit dans son propre thread.
"""
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from ..core.org import organisation_defaut
from ..db import SessionLocal, initialiser_base
from ..ingestion.folder_watcher import demarrer_watcher
from ..ingestion.imap_poller import traiter_boite
from ..models import Facture, FichierSource, StatutFacture, TypeFichier
from ..extraction.service import extraire_facture
from ..ingestion.storage import charger
from ..config import settings

# Seuls les types exacts passent par l'extracteur automatique. Un PDF sale
# (scan) reste `recue` : c'est le travail de l'OCR (sprint 2.5), pas le sien.
TYPES_EXTRACTIBLES = [TypeFichier.XML.value, TypeFichier.PDF_A3_FACTURX.value]


async def poll_imap(context) -> dict:
    """Job récurrent : lit la boîte dédiée, ingère, commit."""
    with SessionLocal() as db:
        org = organisation_defaut(db)
        stats = traiter_boite(db, organisation_id=org.id, acteur="worker:imap")
        db.commit()
    return stats


async def extraire_file(context) -> dict:
    """Job récurrent : extrait les factures reçues dont le type est exact
    (XML Factur-X ou PDF/A-3). Chaque facture est commitée séparément :
    un fichier pourri ne doit jamais bloquer la file."""
    traitees, ratees = 0, 0
    with SessionLocal() as db:
        paires = db.execute(
            select(Facture, FichierSource)
            .join(FichierSource, Facture.fichier_source_id == FichierSource.id)
            .where(
                Facture.statut == StatutFacture.RECUE.value,
                FichierSource.type_detecte.in_(TYPES_EXTRACTIBLES),
            )
        ).all()
        for facture, fichier in paires:
            resume = extraire_facture(
                db,
                facture=facture,
                fichier=fichier,
                contenu=charger(fichier.s3_key),
                acteur="worker:extractor",
            )
            if resume is not None:
                traitees += 1
                if not resume["reussie"]:
                    ratees += 1
            db.commit()
    return {"extraites": traitees, "echecs_traces": ratees}


def _id_org_defaut():
    with SessionLocal() as db:
        return organisation_defaut(db).id


async def demarrage(context) -> None:
    # Les tables sont créées si absentes, sous verrou consultatif :
    # pas de course avec l'api qui fait de son côté au même instant.
    # Alembic remplacera ceci avant la prod (sprint 6).
    initialiser_base()
    if settings.watch_folder:
        context["observer"] = demarrer_watcher(organisation_id=_id_org_defaut())
    # Sinon, mode console : aucun canal actif, l'ingestion passe par l'API.


async def arret(context) -> None:
    observer = context.get("observer")
    if observer is not None:
        observer.stop()
        observer.join()


class WorkerSettings:
    functions = [poll_imap, extraire_file]
    cron_jobs = [
        cron(poll_imap, minute=None, second=0, run_at_startup=True),
        cron(extraire_file, minute=None, second=30),
    ]
    on_startup = demarrage
    on_shutdown = arret
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
