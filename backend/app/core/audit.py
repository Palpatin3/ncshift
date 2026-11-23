"""Service d'audit : la seule porte d'entrée vers le journal.

Append-only. Aucune fonction de modification ou suppression n'existe ici,
et aucun autre module ne doit écrire dans audit_log directement.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import AuditLog, Facture, StatutFacture
from .states import TransitionInvalide, transition_possible


def journaliser(
    db: Session,
    *,
    organisation_id: uuid.UUID,
    entite_type: str,
    entite_id: uuid.UUID,
    evenement: str,
    ancien_statut: str | None = None,
    nouveau_statut: str | None = None,
    acteur: str = "system",
    details: dict | None = None,
) -> AuditLog:
    """Ajoute une ligne d'audit. Ne commet pas : le commit appartient à l'appelant."""
    ligne = AuditLog(
        organisation_id=organisation_id,
        entite_type=entite_type,
        entite_id=entite_id,
        evenement=evenement,
        ancien_statut=ancien_statut,
        nouveau_statut=nouveau_statut,
        acteur=acteur,
        details=details,
        created_at=datetime.now(timezone.utc),
    )
    db.add(ligne)
    db.flush()
    return ligne


def changer_statut(
    db: Session,
    *,
    facture: Facture,
    nouveau_statut: StatutFacture | str,
    acteur: str = "system",
    details: dict | None = None,
) -> Facture:
    """Transitions uniquement par cette fonction : vérifie la légalité,
    écrit la ligne d'audit. Échoue fort sur transition interdite."""
    ancien = StatutFacture(facture.statut)
    cible = StatutFacture(nouveau_statut)
    if not transition_possible(ancien, cible):
        raise TransitionInvalide(
            f"Transition interdite : {ancien.value} -> {cible.value} "
            f"(facture {facture.id})"
        )
    facture.statut = cible.value
    db.flush()
    journaliser(
        db,
        organisation_id=facture.organisation_id,
        entite_type="facture",
        entite_id=facture.id,
        evenement="transition_statut",
        ancien_statut=ancien.value,
        nouveau_statut=cible.value,
        acteur=acteur,
        details=details,
    )
    return facture
