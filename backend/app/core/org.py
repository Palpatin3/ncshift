"""Organisation par défaut. MVP : une entité par client, la console
travaille sur l'organisation du pilote ; le multi-tenant réel (sprint 4)
réutilisera les mêmes lignes, juste filtrées par utilisateur."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Organisation


def organisation_defaut(db: Session) -> Organisation:
    """Retourne l'organisation du pilote, la crée au premier démarrage."""
    org = db.scalar(select(Organisation).limit(1))
    if org is not None:
        return org
    org = Organisation(nom=settings.organisation_defaut, slug=settings.organisation_defaut)
    db.add(org)
    db.flush()
    return org


def organisation_par_id(db: Session, organisation_id: uuid.UUID) -> Organisation | None:
    return db.get(Organisation, organisation_id)
