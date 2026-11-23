"""Score de confiance et avis de l'extraction.

Le XML Factur-X étant exact par construction, un champ présent vaut 1.0 :
les pénalités (multiplicatives, donc lisibles dans l'audit) ne viennent que
des contrôles de cohérence métier :

  - champ critique manquant (numéro, date, TTC, vendeur) : x0.55 chacun ;
  - HT + TVA != TTC (à 2 centimes près) : x0.40, avis `incoherence_montants` ;
  - IBAN imprimé qui ne passe pas la clé mod-97 : x0.50, avis `iban_invalide`.

Sous le seuil (config `SEUIL_CONFIANCE`, 0.85 par défaut), la facture part
en `a_valider` : jamais de données douteuses qui se faufilent en silence.
Chaque champ extrait reste affiché pour l'humain qui valide.
"""
from decimal import Decimal

from .base import DonneesFacture

CHAMPS_CRITIQUES = ("numero", "date_facture", "montant_ttc", "vendeur_nom")
TOLERANCE = Decimal("0.02")  # arrondis d'impression tolérés, pas plus


def iban_valide(iban: str) -> bool:
    """Contrôle mod-97 (norme ISO 13616), pays inclus."""
    iban = (iban or "").replace(" ", "").upper()
    if len(iban) < 15 or not iban.isalnum():
        return False
    reordonne = iban[4:] + iban[:4]
    chiffres = "".join(str(int(c, 36)) for c in reordonne)  # A=10, B=11, ...
    return int(chiffres) % 97 == 1


def noter(donnees: DonneesFacture) -> tuple[float, list[str]]:
    """Retourne (score global dans [0,1], liste d'avis machine-lisibles)."""
    avis: list[str] = []
    score = 1.0

    for champ in CHAMPS_CRITIQUES:
        if not getattr(donnees, champ, None):
            avis.append(f"champ_manquant:{champ}")
            score *= 0.55

    ht, tva, ttc = donnees.montant_ht, donnees.montant_tva, donnees.montant_ttc
    if ht is not None and tva is not None and ttc is not None:
        if abs(ht + tva - ttc) > TOLERANCE:
            avis.append("incoherence_montants")
            score *= 0.40

    if donnees.iban and not iban_valide(donnees.iban):
        avis.append("iban_invalide")
        score *= 0.50

    return round(min(score, 1.0), 3), avis
