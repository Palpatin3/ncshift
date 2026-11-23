"""Watcher du dossier partagé : canal n° 2 du MVP."""
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..config import settings
from ..db import SessionLocal
from ..models import Canal
from ..core.org import organisation_defaut
from .service import enregistrer_fichier

DELAI_STABILISATION_S = 2  # le temps que le copier-coller finisse d'écrire


def _attendre_fichier_stable(path: Path) -> bytes | None:
    """Un fichier déposé par un humain peut être en cours d'écriture :
    on attend que sa taille soit stable avant de le lire."""
    precedente = -1
    for _ in range(10):
        try:
            taille = path.stat().st_size
        except OSError:
            return None
        if taille == precedente and taille > 0:
            return path.read_bytes()
        precedente = taille
        time.sleep(DELAI_STABILISATION_S / 10)
    return None


class GestionnaireDossier(FileSystemEventHandler):
    def __init__(self, organisation_id):
        self.organisation_id = organisation_id
        self.dossier = Path(settings.watch_folder).resolve()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path).resolve()
        if "traite" in path.parts:  # sous-dossier de sortie : ne pas reingérer
            return
        contenu = _attendre_fichier_stable(path)
        if contenu is None:
            return
        with SessionLocal() as db:
            enregistrer_fichier(
                db,
                organisation_id=self.organisation_id,
                nom_fichier=path.name,
                contenu=contenu,
                canal=Canal.DOSSIER.value,
                acteur=f"watcher:{settings.watch_folder}",
            )
            db.commit()
        # Le fichier ne reste pas dans la zone d'entrée : il est déplacé,
        # jamais supprimé (l'original est une pièce comptable).
        sortie = self.dossier / "traites"
        sortie.mkdir(exist_ok=True)
        cible = sortie / path.name
        i = 1
        while cible.exists():
            cible = sortie / f"{path.stem}-{i}{path.suffix}"
            i += 1
        path.rename(cible)


def demarrer_watcher(organisation_id) -> Observer:
    """Démarre l'observation du dossier partagé. Retourne l'Observer
    (à stopper proprement à l'arrêt du worker)."""
    handler = GestionnaireDossier(organisation_id)
    observer = Observer()
    observer.schedule(handler, settings.watch_folder, recursive=False)
    observer.start()
    return observer
