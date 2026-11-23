"""Worker arq : poll IMAP périodique + watcher dossier partagé.

Un seul worker au départ (roadmap : technologies ennuyeuses).
Le poll IMAP tourne chaque minute ; le watcher vit dans son propre thread.
"""
from arq import cron
from arq.connections import RedisSettings

from ..core.org import organisation_defaut
from ..db import SessionLocal, engine, Base
from ..ingestion.folder_watcher import demarrer_watcher
from ..ingestion.imap_poller import traiter_boite
from ..config import settings


async def poll_imap(context) -> dict:
    """Job récurrent : lit la boîte dédiée, ingère, commit."""
    with SessionLocal() as db:
        org = organisation_defaut(db)
        stats = traiter_boite(db, organisation_id=org.id, acteur="worker:imap")
        db.commit()
    return stats


async def demarrage(context) -> None:
    # Les tables sont créées si absentes (sprint 1 ; Alembic avant prod)
    Base.metadata.create_all(bind=engine)
    if settings.watch_folder:
        context["observer"] = demarrer_watcher(organisation_id=_id_org_defaut())
    elif settings.imap_host is None:
        pass  # mode console : aucun canal actif, l'ingestion passe par l'API


def _id_org_defaut():
    with SessionLocal() as db:
        return organisation_defaut(db).id


async def arret(context) -> None:
    observer = context.get("observer")
    if observer is not None:
        observer.stop()
        observer.join()


class WorkerSettings:
    functions = [poll_imap]
    cron_jobs = [cron(poll_imap, minute=None, second=0, run_at_startup=True)]
    on_startup = demarrage
    on_shutdown = arret
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
