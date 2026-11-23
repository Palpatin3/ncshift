"""Enums métier. Stockés en colonnes String (pas d'enum natif PG :
migration plus simple, même vérité côté Python)."""
from enum import Enum


class Canal(str, Enum):
    """D'où vient le fichier."""
    MAIL = "mail"
    DOSSIER = "dossier"
    API = "api"


class TypeFichier(str, Enum):
    """Type détecté par sniffing (jamais l'extension, toujours le contenu)."""
    PDF = "pdf"
    PDF_A3_FACTURX = "pdf_a3_facturx"  # PDF/A-3 avec XML Factur-X embarqué
    XML = "xml"  # UBL ou CII
    AUTRE = "autre"


class StatutFacture(str, Enum):
    """Machine à états d'une facture, voir app/core/states.py."""
    RECUE = "recue"
    EXTRAITE = "extraite"
    CONTROLEE = "controlee"
    A_VALIDER = "a_valider"
    VALIDEE = "validee"
    EXPORTEE = "exportee"
    PAYEE = "payee"
    REJETEE = "rejetee"
