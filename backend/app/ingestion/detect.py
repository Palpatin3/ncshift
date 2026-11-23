"""Détection du type réel d'un fichier : jamais l'extension, toujours le contenu."""
import xml.etree.ElementTree as ET
from io import BytesIO

from pypdf import PdfReader

from ..models.enums import TypeFichier

# Racines XML des formats de facture structurée que le MVP sait lire
RACINES_XML_FACTURE = {"Invoice", "CrossIndustryInvoice"}


def detecter_type(nom_fichier: str, contenu: bytes) -> str:
    """Renvoie une valeur de TypeFichier. Ne lève jamais d'exception :
    un fichier illisible est un fichier `autre`, pas un crash du worker."""
    tete = contenu[:1024].lstrip()
    if tete.startswith(b"%PDF"):
        return _detecter_pdf(contenu)
    if tete.startswith(b"<"):
        return _detecter_xml(contenu)
    return TypeFichier.AUTRE.value


def _detecter_pdf(contenu: bytes) -> str:
    """PDF classique, ou PDF/A-3 portant un XML Factur-X en pièce jointe.

    Le XML embarqué est gratuit et exact : c'est le chemin roi de
    l'extraction (sprint 2), il doit être repéré dès l'ingestion.
    """
    try:
        reader = PdfReader(BytesIO(contenu))
        for nom in getattr(reader, "attachments", {}) or {}:
            nom_bas = (nom or "").lower()
            if "factur-x" in nom_bas or "zugferd" in nom_bas or nom_bas.endswith(".xml"):
                return TypeFichier.PDF_A3_FACTURX.value
    except Exception:
        # PDF illisible : il reste un PDF, le sprint 2 (OCR) avisera.
        pass
    return TypeFichier.PDF.value


def _detecter_xml(contenu: bytes) -> str:
    try:
        racine = ET.fromstring(contenu)
        tag = racine.tag.split("}")[-1]  # ignore le namespace
        if tag in RACINES_XML_FACTURE:
            return TypeFichier.XML.value
    except ET.ParseError:
        pass
    return TypeFichier.AUTRE.value
