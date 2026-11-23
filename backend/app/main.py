"""NCshift : de la facture au paiement. Point d'entrée API (sprint 1)."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import __version__
from .api.routes import console_router, health_router
from .db import Base, engine


@asynccontextmanager
async def demarrage(arret):
    # Sprint 1 : create_all au démarrage. Alembic avant la prod (sprint 6).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="NCshift API", version=__version__, lifespan=demarrage)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # démo locale ; à verrouiller en sprint 6
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(console_router)

_PAGE_CONSOLE = Path(__file__).parent / "static" / "console.html"


@app.get("/", include_in_schema=False)
def console():
    return FileResponse(_PAGE_CONSOLE)
