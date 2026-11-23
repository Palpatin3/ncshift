"""Extraction Factur-X (sprint 2) : exact sur le chemin roi, notée, tracée,
et routée vers l'humain quand le score n'y est pas."""
from datetime import date
from io import BytesIO

from pypdf import PdfWriter
from sqlalchemy import select

from app.extraction.score import iban_valide
from app.extraction.service import extraire_facture
from app.ingestion.service import enregistrer_fichier
from app.models import AuditLog, StatutFacture, TypeFichier
from app.models.extraction import Extraction

CII_EXEMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
 xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
 xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
 xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>FA-2026-001</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime><udt:DateTimeString format="102">20261123</udt:DateTimeString></ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>ACME Industries SAS</ram:Name>
        <ram:SpecifiedLegalOrganization><ram:ID schemeID="0002">123456789</ram:ID></ram:SpecifiedLegalOrganization>
        <ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">FR90123456789</ram:ID></ram:SpecifiedTaxRegistration>
      </ram:SellerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementPaymentMeans>
        <ram:TypeCode>58</ram:TypeCode>
        <ram:PayeePartyCreditorFinancialAccount><ram:IBANID>FR7630006000011234567890189</ram:IBANID></ram:PayeePartyCreditorFinancialAccount>
      </ram:SpecifiedTradeSettlementPaymentMeans>
      <ram:ApplicableTradeTax>
        <ram:CalculatedAmount>40.00</ram:CalculatedAmount>
        <ram:TypeCode>VAT</ram:TypeCode>
        <ram:BasisAmount>200.00</ram:BasisAmount>
        <ram:RateApplicablePercent>20.00</ram:RateApplicablePercent>
      </ram:ApplicableTradeTax>
      <ram:SpecifiedTradePaymentTerms>
        <ram:DueDateDateTime><udt:DateTimeString format="102">20261223</udt:DateTimeString></ram:DueDateDateTime>
      </ram:SpecifiedTradePaymentTerms>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:LineTotalAmount>200.00</ram:LineTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">40.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>240.00</ram:GrandTotalAmount>
        <ram:DuePayableAmount>240.00</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""


def _ingester_facture(db, organisation, nom, contenu):
    resultat = enregistrer_fichier(
        db,
        organisation_id=organisation.id,
        nom_fichier=nom,
        contenu=contenu,
        canal="mail",
    )
    return resultat


def test_xml_seul_extrait_exact(db, organisation):
    resultat = _ingester_facture(db, organisation, "facture-acme.xml", CII_EXEMPLE)
    resume = extraire_facture(
        db, facture=resultat.facture, fichier=resultat.fichier, contenu=CII_EXEMPLE
    )
    assert resume["reussie"] is True
    facture = resultat.facture
    assert facture.statut == StatutFacture.EXTRAITE.value
    assert facture.numero == "FA-2026-001"
    assert facture.date_facture == date(2026, 11, 23)
    assert facture.date_echeance == date(2026, 12, 23)
    assert float(facture.montant_ht) == 200.00
    assert float(facture.montant_ttc) == 240.00
    assert facture.devise == "EUR"
    assert facture.score_confiance is not None and facture.score_confiance >= 0.85

    ligne = db.scalar(select(Extraction).where(Extraction.facture_id == facture.id))
    assert ligne is not None and ligne.reussie is True
    assert ligne.donnees["vendeur_nom"] == "ACME Industries SAS"
    assert ligne.donnees["vendeur_siren"] == "123456789"
    assert ligne.donnees["iban"] == "FR7630006000011234567890189"
    assert ligne.donnees["tva_par_taux"] == [{"taux": 20.0, "base": 200.0, "tva": 40.0}]

    evenements = db.scalars(
        select(AuditLog).where(AuditLog.entite_id == facture.id)
    ).all()
    assert [e.evenement for e in evenements] == [
        "recue", "extraction", "transition_statut",
    ]


def test_pdf_avec_xml_embarque_extrait(db, organisation):
    """Le chemin roi complet : PDF/A-3 Factur-X détecté à l'ingestion,
    XML relu depuis la pièce jointe, facture extraite automatiquement."""
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_attachment("factur-x.xml", CII_EXEMPLE)
    tampon = BytesIO()
    writer.write(tampon)
    pdf = tampon.getvalue()

    resultat = _ingester_facture(db, organisation, "facture-acme.pdf", pdf)
    assert resultat.fichier.type_detecte == TypeFichier.PDF_A3_FACTURX.value

    resume = extraire_facture(
        db, facture=resultat.facture, fichier=resultat.fichier, contenu=pdf
    )
    assert resume["reussie"] is True
    assert resultat.facture.statut == StatutFacture.EXTRAITE.value
    assert resultat.facture.numero == "FA-2026-001"
    assert float(resultat.facture.montant_ttc) == 240.00
    assert resume["methode"] == "facturx_xml"


def test_score_bas_route_la_facture_vers_validation_humaine(db, organisation):
    """Numéro absent + TTC incohérent : la machine ne fait pas semblant,
    la facture file en `a_valider` avec un avis machine-lisible."""
    casse = CII_EXEMPLE.replace(b"<ram:ID>FA-2026-001</ram:ID>", b"<ram:ID></ram:ID>")
    casse = casse.replace(b"240.00", b"999.00")
    resultat = _ingester_facture(db, organisation, "facture-merdeuse.xml", casse)
    resume = extraire_facture(
        db, facture=resultat.facture, fichier=resultat.fichier, contenu=casse
    )
    facture = resultat.facture
    assert facture.statut == StatutFacture.A_VALIDER.value
    assert facture.score_confiance < 0.85
    assert "champ_manquant:numero" in resume["avis"]
    assert "incoherence_montants" in resume["avis"]

    evenements = db.scalars(
        select(AuditLog).where(AuditLog.entite_id == facture.id)
    ).all()
    assert [e.evenement for e in evenements] == [
        "recue", "extraction", "transition_statut",
        "score_faible", "transition_statut",
    ]


def test_iban_imprime_invalide_penalise(db, organisation):
    casse = CII_EXEMPLE.replace(
        b"FR7630006000011234567890189", b"FR7630006000011234567890188"
    )
    resultat = _ingester_facture(db, organisation, "facture-iban-douteux.xml", casse)
    resume = extraire_facture(
        db, facture=resultat.facture, fichier=resultat.fichier, contenu=casse
    )
    assert "iban_invalide" in resume["avis"]
    assert resultat.facture.statut == StatutFacture.A_VALIDER.value
    assert iban_valide("FR7630006000011234567890189") is True
    assert iban_valide("FR7630006000011234567890188") is False


def test_ubl_non_supporte_trace_sans_crash(db, organisation):
    """UBL (détection XML correcte) mais parsing CII attendu : échec tracé,
    la facture reste `recue`, rien ne se perd."""
    ubl = b'<?xml version="1.0"?><Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"><cbc:ID>UBL-1</cbc:ID></Invoice>'
    resultat = _ingester_facture(db, organisation, "facture-ubl.xml", ubl)
    resume = extraire_facture(
        db, facture=resultat.facture, fichier=resultat.fichier, contenu=ubl
    )
    assert resume["reussie"] is False
    assert resume["raison"].startswith("format_non_supporte")
    assert resultat.facture.statut == StatutFacture.RECUE.value

    echec = db.scalar(
        select(Extraction).where(Extraction.reussie.is_(False), Extraction.facture_id == resultat.facture.id)
    )
    assert echec is not None
    evenements = db.scalars(
        select(AuditLog).where(
            AuditLog.entite_id == resultat.facture.id,
            AuditLog.evenement == "extraction_echouee",
        )
    ).all()
    assert len(evenements) == 1


def test_aucun_moteur_renvoie_none(db, organisation):
    from io import BytesIO as B
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    tampon = B()
    writer.write(tampon)

    resultat = _ingester_facture(db, organisation, "scan-sale.pdf", tampon.getvalue())
    assert resultat.facture is not None
    # PDF sale : aucun moteur ne sait encore l'extraire (OCR au sprint 2.5)
    resume = extraire_facture(
        db, facture=resultat.facture, fichier=resultat.fichier, contenu=tampon.getvalue()
    )
    assert resume is None
    assert resultat.facture.statut == StatutFacture.RECUE.value
