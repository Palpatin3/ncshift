from fastapi import APIRouter

from ...db import engine
from ... import __version__

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict:
    """Sonde minimale : la base répond."""
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "version": __version__}
