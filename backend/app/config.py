"""Configuration NCshift : tout vient de l'environnement ou d'un fichier .env.

Aucune valeur sensible ne doit être commitée. En dev, docker-compose fournit
des valeurs par défaut saines ; en prod, les secrets sont dans l'env du VPS.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "NCshift"
    env: str = "dev"  # dev | prod

    # Base et file
    database_url: str = "postgresql+psycopg://ncshift:ncshift@db:5432/ncshift"
    redis_url: str = "redis://redis:6379/0"

    # Stockage des fichiers bruts. Les PDF ne vont jamais en base.
    # "s3" : S3-compatible (Scaleway en prod) ;
    # "local" : dossier monté (dev, démo, tests d'intégration) ;
    # "off" : aucune copie (tests unitaires).
    # Note : MinIO a quitté Docker Hub en septembre 2026, le socle ne dépend
    # donc plus d'aucun serveur S3 local : en dev on écrit dans un volume,
    # en prod on branche le S3 réel sans changer le reste du code.
    stockage: str = "s3"
    stockage_local_dir: str = "/data"
    s3_endpoint_url: str = "https://s3.fr-par.scw.cloud"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "ncshift"

    # Boîte mail dédiée (IMAP)
    imap_host: str | None = None
    imap_port: int = 993
    imap_user: str | None = None
    imap_password: str | None = None
    imap_folder: str = "INBOX"
    imap_process_folder: str = "NCshift-traites"

    # Dossier partagé (watcher)
    watch_folder: str | None = None

    # Organisation par défaut (MVP : une entité par client)
    organisation_defaut: str = "pilote"

    # Extraction (sprint 2) : sous ce score de confiance, une facture extraite
    # part en `a_valider` plutôt que d'être considérée comme sûre. 0.85 : les
    # pénalités d'un seul champ critique manquant (x0.55) passent sous le seuil.
    seuil_confiance: float = 0.85

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
