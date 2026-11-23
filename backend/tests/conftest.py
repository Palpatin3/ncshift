import os

# Avant tout import applicatif : les tests tournent sur SQLite en mémoire,
# sans S3 (l'ingestion doit être testable sans infrastructure).
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["STOCKER_S3"] = "false"

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Organisation


@pytest.fixture()
def db():
    moteur = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(moteur)
    fabrique = sessionmaker(bind=moteur, autoflush=False, expire_on_commit=False)
    session = fabrique()
    try:
        yield session
    finally:
        session.close()
        moteur.dispose()


@pytest.fixture()
def organisation(db):
    org = Organisation(nom="Pilote SARL", slug="pilote")
    db.add(org)
    db.commit()
    return org
