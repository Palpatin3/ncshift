"""Stockage S3 des fichiers bruts. Les PDF ne vont jamais en base."""
import boto3

from ..config import settings


def client_s3():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )


def televerser(contenu: bytes, cle: str) -> str:
    """Dépose le fichier dans le bucket (créé au besoin) et renvoie la clé."""
    client = client_s3()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.s3_bucket)
    client.put_object(Bucket=settings.s3_bucket, Key=cle, Body=contenu)
    return cle
