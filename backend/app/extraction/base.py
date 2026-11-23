"""Contrat commun des extracteurs (sprint 2).

Un extracteur lit le contenu brut d'un fichier et en tire le modèle unifié
`DonneesFacture`. Le premier moteur est le XML Factur-X (exact et gratuit) ;
l'OCR + LLM Mistral (sprint 2.5) branchera la même interface.

Règle : jamais de champ inventé. Ce qui n'est pas dans le fichier reste à None,
c'est le score de confiance qui dira si la facture est automatique ou humaine.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable


class ExtractionErreur(Exception):
    """Le fichier ne peut pas être extrait par ce moteur, avec la raison
    machine-lisible (`raison`), à journaliser dans l'audit, jamais à masquer."""

    def __init__(self, raison: str):
        super().__init__(raison)
        self.raison = raison


@dataclass
class DonneesFacture:
    """Le modèle unifié : ce que tout extracteur doit produire, d'où qu'il vienne."""

    numero: str | None = None
    date_facture: str | None = None  # ISO YYYY-MM-DD
    date_echeance: str | None = None  # ISO YYYY-MM-DD
    devise: str = "EUR"
    vendeur_nom: str | None = None
    vendeur_siren: str | None = None
    vendeur_tva: str | None = None
    iban: str | None = None  # celui imprimé sur la facture ; le référentiel tranchera
    montant_ht: Decimal | None = None
    montant_tva: Decimal | None = None
    montant_ttc: Decimal | None = None
    tva_par_taux: list[dict] = field(default_factory=list)  # [{taux, base, tva}]

    def vers_json(self) -> dict:
        def _plat(v: Any) -> Any:
            return float(v) if isinstance(v, Decimal) else v

        return {
            "numero": self.numero,
            "date_facture": self.date_facture,
            "date_echeance": self.date_echeance,
            "devise": self.devise,
            "vendeur_nom": self.vendeur_nom,
            "vendeur_siren": self.vendeur_siren,
            "vendeur_tva": self.vendeur_tva,
            "iban": self.iban,
            "montant_ht": _plat(self.montant_ht),
            "montant_tva": _plat(self.montant_tva),
            "montant_ttc": _plat(self.montant_ttc),
            "tva_par_taux": [
                {k: _plat(x) for k, x in ligne.items()} for ligne in self.tva_par_taux
            ],
        }


@runtime_checkable
class Extracteur(Protocol):
    """Toute brique d'extraction expose ceci. Le service choisit le bon
    extracteur selon le type détecté à l'ingestion (jamais l'extension)."""

    nom: str

    def peut_extraire(self, type_fichier: str) -> bool: ...

    def extraire(self, contenu: bytes, type_fichier: str) -> DonneesFacture:
        """Lève `ExtractionErreur` si le contenu ne collabore pas."""
