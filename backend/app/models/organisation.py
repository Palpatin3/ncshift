import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .base import TimestampMixin


class Organisation(Base, TimestampMixin):
    """Le client. MVP : une entité juridique par organisation."""

    __tablename__ = "organisation"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    actif: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Organisation {self.slug}>"
