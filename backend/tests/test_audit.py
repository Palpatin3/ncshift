"""Le journal d'audit : personne ne doit pouvoir changer une ligne."""
import pytest
from sqlalchemy import select

from app.core.audit import changer_statut, journaliser
from app.core.states import TransitionInvalide
from app.models import AuditLog, StatutFacture


def test_journaliser_ajoute_sans_modifier(db, organisation):
    journaliser(
        db,
        organisation_id=organisation.id,
        entite_type="organisation",
        entite_id=organisation.id,
        evenement="test_ecriture",
    )
    ligne = db.scalar(select(AuditLog).where(AuditLog.evenement == "test_ecriture"))
    assert ligne is not None
    assert ligne.ancien_statut is None


def test_transition_interdite_leve_et_ne_triche_pas(db, organisation):
    from app.ingestion.service import enregistrer_fichier
    from io import BytesIO
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    tampon = BytesIO()
    writer.write(tampon)

    resultat = enregistrer_fichier(
        db,
        organisation_id=organisation.id,
        nom_fichier="f.pdf",
        contenu=tampon.getvalue(),
        canal="mail",
    )
    db.commit()
    facture = resultat.facture

    # recue -> payee est impossible
    with pytest.raises(TransitionInvalide):
        changer_statut(db, facture=facture, nouveau_statut=StatutFacture.PAYEE)
    db.rollback()
    assert facture.statut == StatutFacture.RECUE.value
    lignes = db.scalars(select(AuditLog).where(AuditLog.entite_id == facture.id)).all()
    assert len(lignes) == 1  # seulement l'audit de réception
