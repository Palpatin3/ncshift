"""NCshift : de la facture au paiement. Point d'entrée API (sprint 1)."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import __version__
from .api.routes import console_router, health_router
from .db import initialiser_base


@asynccontextmanager
async def demarrage(arret):
    # Sprint 1 : create_all au démarrage, protégé par un verrou consultatif
    # (api et worker démarrent ensemble sur une base vierge).
    # Alembic avant la prod (sprint 6).
    initialiser_base()
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

_DOSSIER_STATIQUE = Path(__file__).parent / "static"
_PAGE_CONSOLE = _DOSSIER_STATIQUE / "console.html"
_LOGO = _DOSSIER_STATIQUE / "logo.png"
_FAVICON = _DOSSIER_STATIQUE / "favicon.png"


@app.get("/", include_in_schema=False)
def console():
    return FileResponse(_PAGE_CONSOLE)


# La marque ne change pas à chaque déploiement : cache long, Immutable
# mais FileResponse ne pose pas encore les headers de cache (sprint 6 ;
# le logo est servi au pire une fois par build chez chaque visiteur).
@app.get("/logo.png", include_in_schema=False)
def logo():
    return FileResponse(_LOGO, media_type="image/png")


@app.get("/favicon.png", include_in_schema=False)
def favicon():
    return FileResponse(_FAVICON, media_type="image/png")
