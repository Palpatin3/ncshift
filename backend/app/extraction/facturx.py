"""Extracteur Factur-X : le chemin roi, exact et gratuit.

Factur-X (profils Minimum à EN 16931) repose sur le CII
(CrossIndustryInvoice). Le XML arrive soit seul (pièce jointe de mail),
soit embarqué dans un PDF/A-3 : la détection a déjà tranché à l'ingestion,
on relit ici la même source de vérité.

Le parsing navigue par noms locaux, insensible aux variations de préfixes
de namespace entre générateurs : les balises comptent, pas les alias.
"""
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from pypdf import PdfReader

from ..models.enums import TypeFichier
from .base import DonneesFacture, ExtractionErreur

# Noms de pièces jointes acceptés comme XML Factur-X embarqué
MARQUEURS_PIECE = ("factur-x", "zugferd", ".xml")


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _enfant(el: ET.Element, nom: str) -> ET.Element | None:
    for enfant in el:
        if _local(enfant.tag) == nom:
            return enfant
    return None


def _tous(el: ET.Element, nom: str) -> list[ET.Element]:
    return [e for e in el if _local(e.tag) == nom]


def _descendant(el: ET.Element, *chemin: str) -> ET.Element | None:
    courant = el
    for nom in chemin:
        courant = _enfant(courant, nom)
        if courant is None:
            return None
    return courant


def _texte(el: ET.Element | None, *chemin: str) -> str | None:
    cible = _descendant(el, *chemin) if el is not None else None
    if cible is None or cible.text is None:
        return None
    texte = cible.text.strip()
    return texte or None


def _decimal(texte: str | None) -> Decimal | None:
    if texte is None:
        return None
    try:
        return Decimal(texte)
    except InvalidOperation:
        return None


def _date_cii(node: ET.Element | None) -> str | None:
    """Format CII 102 = AAAAMMJJ ; ISO en secours, sinon None."""
    if node is None or not node.text:
        return None
    texte = node.text.strip()
    for format_ in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(texte, format_).date().isoformat()
        except ValueError:
            continue
    return None


class ExtracteurFacturX:
    nom = "facturx_xml"

    def peut_extraire(self, type_fichier: str) -> bool:
        return type_fichier in {TypeFichier.XML.value, TypeFichier.PDF_A3_FACTURX.value}

    def extraire(self, contenu: bytes, type_fichier: str) -> DonneesFacture:
        if type_fichier == TypeFichier.PDF_A3_FACTURX.value:
            contenu = self._xml_embarque(contenu)
        return self._parse_cii(contenu)

    def _xml_embarque(self, pdf: bytes) -> bytes:
        try:
            lecteur = PdfReader(BytesIO(pdf))
        except Exception as e:
            raise ExtractionErreur(f"pdf_illisible:{type(e).__name__}") from e
        pieces = getattr(lecteur, "attachments", None) or {}
        for nom, contenu in pieces.items():
            bas = (nom or "").lower()
            if any(marqueur in bas for marqueur in MARQUEURS_PIECE):
                if isinstance(contenu, list):
                    contenu = contenu[0] if contenu else None
                if contenu:
                    return contenu
        raise ExtractionErreur("xml_embarque_introuvable")

    def _parse_cii(self, xml: bytes) -> DonneesFacture:
        try:
            racine = ET.fromstring(xml)
        except ET.ParseError:
            raise ExtractionErreur("xml_illisible")
        if _local(racine.tag) != "CrossIndustryInvoice":
            # UBL et autres variants : après le CII, qui domine en France.
            raise ExtractionErreur(f"format_non_supporte:{_local(racine.tag)}")

        doc = _enfant(racine, "ExchangedDocument")
        numero = _texte(doc, "ID")
        date_facture = _date_cii(_descendant(doc, "IssueDateTime", "DateTimeString"))

        transaction = _descendant(racine, "SupplyChainTradeTransaction")
        accord = _descendant(transaction, "ApplicableHeaderTradeAgreement")
        vendeur = _descendant(accord, "SellerTradeParty")
        nom_vendeur = _texte(vendeur, "Name")
        siren = self._siren(vendeur)
        tva_vendeur = _texte(vendeur, "SpecifiedTaxRegistration", "ID")

        reglement = _descendant(transaction, "ApplicableHeaderTradeSettlement")
        devise = _texte(reglement, "InvoiceCurrencyCode") or "EUR"
        moyens = _descendant(reglement, "SpecifiedTradeSettlementPaymentMeans")
        iban = _texte(moyens, "PayeePartyCreditorFinancialAccount", "IBANID")
        echeance = _date_cii(
            _descendant(reglement, "SpecifiedTradePaymentTerms", "DueDateDateTime", "DateTimeString")
        )

        tva_par_taux: list[dict] = []
        for taxe in _tous(reglement, "ApplicableTradeTax") if reglement is not None else []:
            tva_par_taux.append(
                {
                    "taux": _decimal(_texte(taxe, "RateApplicablePercent")),
                    "base": _decimal(_texte(taxe, "BasisAmount")),
                    "tva": _decimal(_texte(taxe, "CalculatedAmount")),
                }
            )

        somme = _descendant(reglement, "SpecifiedTradeSettlementHeaderMonetarySummation")
        ht = _decimal(_texte(somme, "LineTotalAmount"))
        total_tva = _decimal(_texte(somme, "TaxTotalAmount"))
        if total_tva is None and tva_par_taux:
            # Somme des lignes de TVA en secours si le total absent
            total_tva = sum((l["tva"] or Decimal(0)) for l in tva_par_taux)
        ttc = _decimal(_texte(somme, "GrandTotalAmount"))
        if ttc is None:
            ttc = _decimal(_texte(somme, "DuePayableAmount"))

        return DonneesFacture(
            numero=numero,
            date_facture=date_facture,
            date_echeance=echeance,
            devise=devise,
            vendeur_nom=nom_vendeur,
            vendeur_siren=siren,
            vendeur_tva=tva_vendeur,
            iban=iban,
            montant_ht=ht,
            montant_tva=total_tva,
            montant_ttc=ttc,
            tva_par_taux=tva_par_taux,
        )

    @staticmethod
    def _siren(vendeur: ET.Element | None) -> str | None:
        """SIREN : schemeID 0002 (9 chiffres) ou GlobalID SIRET (14 → 9)."""
        if vendeur is None:
            return None
        orga = _descendant(vendeur, "SpecifiedLegalOrganization", "ID")
        if orga is not None and orga.text:
            valeur = orga.text.strip()
            if len(valeur) == 14:  # SIRET
                return valeur[:9]
            return valeur
        global_id = _descendant(vendeur, "GlobalID")
        if global_id is not None and global_id.text:
            valeur = global_id.text.strip()
            return valeur[:9] if len(valeur) == 14 else valeur
        return None
