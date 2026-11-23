import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class AuditLog(Base):
    """Journal d'audit append-only.

    Règle absolue : aucune ligne ne doit jamais être modifiée ni supprimée
    par le code applicatif. Chaque changement d'état d'une facture, chaque
    fichier reçu ou ignoré, chaque contrôles produisent une ligne ici.
    Ce module n'expose volontairement aucune fonction de mise à jour.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organisation.id"), nullable=False, index=True
    )
    entite_type: Mapped[str] = mapped_column(String(64), nullable=False)  # facture | fichier_source | organisation
    entite_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    evenement: Mapped[str] = mapped_column(String(64), nullable=False)
    ancien_statut: Mapped[str | None] = mapped_column(String(32), nullable=True)
    nouveau_statut: Mapped[str | None] = mapped_column(String(32), nullable=True)
    acteur: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
