"""Stockage des fichiers bruts : S3 (prod) ou dossier local (dev/démo).

L'adresse de stockage (la clé) est la même dans les deux cas, seul le backend
change. MinIO a quitté Docker Hub en septembre 2026 : plutôt que de dépendre
d'images gelées, le dev tourne sur un dossier monté et la prod branche le
S3-compatible de Scaleway. L'interface `televerser` ne change pas.
"""
from pathlib import Path

import boto3

from ..config import settings


def televerser(contenu: bytes, cle: str) -> str:
    """Dépose le fichier et renvoie la clé. Échoue fort si le backend
    est mal configuré : perdre un fichier silencieusement est inacceptable."""
    if settings.stockage == "local":
        return _televerser_local(contenu, cle)
    return _televerser_s3(contenu, cle)


def charger(cle: str | None) -> bytes | None:
    """Relit un fichier brut déposé (symétrique de `televerser`).

    Renvoie None si la clé est absente. En revanche, un fichier dont la clé
    existe mais illisible est un incident : l'exception remonte et sera
    journalisée par le service d'extraction.
    """
    if not cle:
        return None
    if settings.stockage == "local":
        return (Path(settings.stockage_local_dir) / cle).read_bytes()
    return _charger_s3(cle)


def _televerser_local(contenu: bytes, cle: str) -> str:
    chemin = Path(settings.stockage_local_dir) / cle
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(contenu)
    return cle


def _charger_s3(cle: str) -> bytes:
    client = _client_s3()
    reponse = client.get_object(Bucket=settings.s3_bucket, Key=cle)
    return reponse["Body"].read()


def _client_s3():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )


def _televerser_s3(contenu: bytes, cle: str) -> str:
    client = _client_s3()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.s3_bucket)
    client.put_object(Bucket=settings.s3_bucket, Key=cle, Body=contenu)
    return cle
