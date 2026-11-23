import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .base import TimestampMixin
from .enums import StatutFacture


class Fournisseur(Base, TimestampMixin):
    """Fiche fournisseur du référentiel propre (alimenté en sprint 3).

    SIREN = clé d'identité normalisée ; IBAN = celui validé au référentiel,
    jamais celui imprimé sur une facture reçue.
    """

    __tablename__ = "fournisseur"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organisation.id"), nullable=False, index=True
    )
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    siren: Mapped[str] = mapped_column(String(9), nullable=True, index=True)
    iban: Mapped[str] = mapped_column(String(35), nullable=True)


class Facture(Base, TimestampMixin):
    """Une facture fournisseur, de sa réception à son paiement.

    Les montants sont saisis au sprint 2 (extraction) ; le sprint 1 crée
    la ligne dès qu'un fichier facture est accepté, dans l'état `recue`.
    """

    __tablename__ = "facture"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organisation.id"), nullable=False, index=True
    )
    fichier_source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fichier_source.id"), nullable=False, index=True
    )
    fournisseur_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fournisseur.id"), nullable=True
    )

    statut: Mapped[str] = mapped_column(
        String(32), nullable=False, default=StatutFacture.RECUE.value, index=True
    )
    numero: Mapped[str | None] = mapped_column(String(64), nullable=True)
    date_facture: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_echeance: Mapped[date | None] = mapped_column(Date, nullable=True)
    montant_ht: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    montant_ttc: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    devise: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    score_confiance: Mapped[float | None] = mapped_column(nullable=True)
