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

    # Stockage S3 (PDF jamais en base). En dev local, stocker_s3=False
    # permet de tourner sans MinIO (utile pour les tests unitaires).
    stocker_s3: bool = True
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
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

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
