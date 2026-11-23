"""Session et base déclarative."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialiser_base() -> None:
    """Crée les tables si absentes, sans course entre processus.

    Au démarrage du compose, api et worker exécutent ceci au même moment
    sur une base vierge. Sans verrou, PostgreSQL lève une UniqueViolation
    sur pg_type (deux CREATE TABLE concurrents). Le verrou consultatif
    sérialise : le premier crée, le second attend, revérifie et ne crée rien.
    """
    if engine.url.get_backend_name() == "sqlite":
        Base.metadata.create_all(bind=engine)
        return
    with engine.begin() as conn:
        conn.exec_driver_sql("SELECT pg_advisory_xact_lock(20261123)")
        Base.metadata.create_all(bind=conn)
