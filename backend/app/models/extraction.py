import uuid

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .base import TimestampMixin


class Extraction(Base, TimestampMixin):
    """Une tentative d'extraction des données d'une facture.

    Append-only comme le journal : chaque essai (réussi ou non) est
    conservé, avec les données extraites, le score et les avis. La facture
    porte les colonnes métier (numéro, montants...) ; ici on garde la trace
    complète, qui alimentera le jeu d'or et le suivi qualité de l'OCR.
    """

    __tablename__ = "extraction"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organisation.id"), nullable=False, index=True
    )
    facture_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facture.id"), nullable=False, index=True
    )
    methode: Mapped[str] = mapped_column(String(32), nullable=False)  # facturx_xml | ocr_llm
    reussie: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    donnees: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    avis: Mapped[list | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
