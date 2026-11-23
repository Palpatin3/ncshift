"""Détection par le contenu : le chemin roi (PDF/A-3 Factur-X) doit être vu."""
from io import BytesIO

from pypdf import PdfWriter

from app.ingestion.detect import detecter_type
from app.models import TypeFichier


def _pdf(nom_piece_jointe=None, contenu_pj=None):
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    if nom_piece_jointe:
        writer.add_attachment(nom_piece_jointe, contenu_pj)
    tampon = BytesIO()
    writer.write(tampon)
    return tampon.getvalue()


def test_pdf_simple():
    assert detecter_type("facture.pdf", _pdf()) == TypeFichier.PDF.value


def test_pdf_factur_x_reconnu_malgre_nimporte_quelle_extension():
    contenu = _pdf("factur-x.xml", b"<Invoice></Invoice>")
    assert detecter_type("document.pdf", contenu) == TypeFichier.PDF_A3_FACTURX.value


def test_pdf_zugferd_reconnu():
    contenu = _pdf("ZUGFeRD-invoice.xml", b"<Invoice></Invoice>")
    assert detecter_type("rechnung.pdf", contenu) == TypeFichier.PDF_A3_FACTURX.value


def test_xml_ubl():
    contenu = b'<?xml version="1.0"?><Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"></Invoice>'
    assert detecter_type("facture.xml", contenu) == TypeFichier.XML.value


def test_xml_cii():
    contenu = b'<?xml version="1.0"?><rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard"></rsm:CrossIndustryInvoice>'
    assert detecter_type("facture.xml", contenu) == TypeFichier.XML.value


def test_xml_non_facture_est_autre():
    assert detecter_type("commande.xml", b"<Order></Order>") == TypeFichier.AUTRE.value


def test_autre_binaire():
    assert detecter_type("photo.jpg", b"\xff\xd8\xff\xe0JFIF") == TypeFichier.AUTRE.value


def test_fichier_corrompu_ne_fait_pas_planter():
    assert detecter_type("bidule.pdf", b"%PDF-\xff\xfe casse") == TypeFichier.PDF.value
