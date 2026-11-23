import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .base import TimestampMixin
from .enums import Canal, TypeFichier


class FichierSource(Base, TimestampMixin):
    """Un fichier entrant, quelle que soit son origine.

    Le dédoublonnage se fait sur (organisation_id, sha256) : le même fichier
    reçu deux fois, même sous deux noms différents, ne passe qu'une fois.
    """

    __tablename__ = "fichier_source"
    __table_args__ = (UniqueConstraint("organisation_id", "sha256", name="uq_org_sha256"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organisation.id"), nullable=False, index=True
    )
    nom_fichier: Mapped[str] = mapped_column(String(512), nullable=False)
    canal: Mapped[str] = mapped_column(String(16), nullable=False)  # Canal
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    type_detecte: Mapped[str] = mapped_column(String(32), nullable=False)  # TypeFichier
    taille_octets: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=True)
    message_id: Mapped[str] = mapped_column(String(255), nullable=True)  # uid IMAP
    recu_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
