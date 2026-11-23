"""Ingestion : dédoublonnage par empreinte, facture créée dans `recue`,
fichiers non factures acceptés mais non facturés, audit systématique."""
from io import BytesIO

from pypdf import PdfWriter
from sqlalchemy import select

from app.core.audit import changer_statut
from app.ingestion.service import enregistrer_fichier
from app.models import AuditLog, Facture, FichierSource, StatutFacture, TypeFichier


def _pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    tampon = BytesIO()
    writer.write(tampon)
    return tampon.getvalue()


def _ingester(db, organisation, nom, contenu):
    return enregistrer_fichier(
        db,
        organisation_id=organisation.id,
        nom_fichier=nom,
        contenu=contenu,
        canal="mail",
    )


def test_facture_pdf_recue(db, organisation):
    resultat = _ingester(db, organisation, "facture-acme.pdf", _pdf())
    assert resultat.nouveau is True
    assert resultat.facture is not None
    assert resultat.facture.statut == StatutFacture.RECUE.value
    assert resultat.fichier.type_detecte == TypeFichier.PDF.value


def test_doublon_ignore_et_trace(db, organisation):
    contenu = _pdf()
    _ingester(db, organisation, "facture-acme.pdf", contenu)
    resultat2 = _ingester(db, organisation, "RENOMMEE.pdf", contenu)  # même contenu, autre nom
    assert resultat2.nouveau is False
    assert resultat2.facture is None
    # Une seule ligne fichier_source, un seul doublon tracé
    fichiers = db.scalars(select(FichierSource)).all()
    assert len(fichiers) == 1
    evenements = db.scalars(select(AuditLog).where(AuditLog.evenement == "doublon_ignore")).all()
    assert len(evenements) == 1
    assert evenements[0].details["nom_recu"] == "RENOMMEE.pdf"


def test_piece_non_facture_pas_de_facture(db, organisation):
    resultat = _ingester(db, organisation, "logo.jpg", b"\xff\xd8\xff\xe0JFIF")
    assert resultat.nouveau is True
    assert resultat.facture is None
    assert resultat.fichier.type_detecte == TypeFichier.AUTRE.value
    # ... mais le fichier reçu est bien tracé dans le journal
    evenements = db.scalars(select(AuditLog).where(AuditLog.evenement == "fichier_recu")).all()
    assert len(evenements) == 1


def test_aucun_changement_sans_audit(db, organisation):
    resultat = _ingester(db, organisation, "facture.pdf", _pdf())
    db.commit()
    changer_statut(db, facture=resultat.facture, nouveau_statut=StatutFacture.EXTRAITE, acteur="test")
    changer_statut(db, facture=resultat.facture, nouveau_statut=StatutFacture.A_VALIDER, acteur="test")
    db.commit()
    lignes = db.scalars(
        select(AuditLog).where(AuditLog.entite_id == resultat.facture.id)
    ).all()
    # recue + 2 transitions = 3 lignes minimum, dans l'ordre
    assert [l.nouveau_statut for l in lignes] == [StatutFacture.RECUE.value, "extraite", "a_valider"]
    assert {l.acteur for l in lignes} == {"test", "system"}
