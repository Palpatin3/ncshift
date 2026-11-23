"""Jeu d'or NCshift : rejouer des factures réelles et vérifier l'extraction.

Règle du jeu : chaque échantillon est un dossier dans `echantillons/`
contenant `facture.xml` (ou `facture.pdf`) et `attendu.json`. Le script
rejoue l'extraction et compare champ à champ.

Un échantillon qui échoue veut dire une régression ou un cas fournisseur
nouveau : on corrige l'extracteur (ou on ajoute l'avis qui baisse le score),
puis l'échantillon redevient vert. Le jeu d'or ne fait que croître.

Usage (backend installé : pip install -e "backend[dev]") :

    python jeu_or/evaluer.py            # tout le jeu
    python jeu_or/evaluer.py acme       # filtre par nom de dossier

Code retour 0 (vert) ou 1 (au moins un rouge) : prêt pour la CI.
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

RACINE = Path(__file__).parent
TOLERANCE = Decimal("0.005")  # au centime d'arrondi


def _comparer(attendu, obtenu, chemin=""):
    """Compare deux structures JSON : seuls les champs listés dans `attendu`
    comptent (le reste de l'extraction est libre d'être plus riche)."""
    erreurs = []
    if isinstance(attendu, dict):
        if not isinstance(obtenu, dict):
            return [f"{chemin} : objet attendu, obtenu {type(obtenu).__name__}"]
        for cle, valeur in attendu.items():
            erreurs += _comparer(valeur, obtenu.get(cle), f"{chemin}.{cle}" if chemin else cle)
    elif isinstance(attendu, list):
        if not isinstance(obtenu, list) or len(obtenu) != len(attendu):
            return [f"{chemin} : {len(attendu)} élément(s) attendu(s), obtenu {len(obtenu) if isinstance(obtenu, list) else 'autre chose'}"]
        for i, (a, o) in enumerate(zip(attendu, obtenu)):
            erreurs += _comparer(a, o, f"{chemin}[{i}]")
    elif isinstance(attendu, (int, float)) and not isinstance(attendu, bool):
        # Montants : comparaison décimale, pas binaire flottante
        if obtenu is None or not isinstance(obtenu, (int, float)):
            erreurs.append(f"{chemin} : nombre attendu, obtenu {obtenu!r}")
        elif abs(Decimal(str(attendu)) - Decimal(str(obtenu))) > TOLERANCE:
            erreurs.append(f"{chemin} : attendu {attendu}, obtenu {obtenu}")
    else:
        if attendu != obtenu:
            erreurs.append(f"{chemin} : attendu {attendu!r}, obtenu {obtenu!r}")
    return erreurs


def _jouer_echantillon(dossier: Path) -> tuple[bool, list[str]]:
    try:
        from app.extraction.facturx import ExtracteurFacturX
        from app.extraction.score import noter
    except ImportError:
        return False, [
            "backend non installé : lancez `pip install -e \"backend[dev]\"` depuis la racine du projet"
        ]

    attendu_brut = json.loads((dossier / "attendu.json").read_text(encoding="utf-8"))
    attendu, score_mini = attendu_brut.get("attendu", {}), attendu_brut.get("score_mini", 0.85)

    pdf = dossier / "facture.pdf"
    source = dossier / "facture.xml"
    type_fichier = "xml"
    if pdf.exists():
        source, type_fichier = pdf, "pdf_a3_facturx"
    if not source.exists():
        return False, ["aucun fichier facture.xml ni facture.pdf dans l'échantillon"]

    try:
        donnees = ExtracteurFacturX().extraire(source.read_bytes(), type_fichier)
    except Exception as e:
        return False, [f"extraction échouée : {e}"]

    erreur_champs = _comparer(attendu, donnees.vers_json())
    score, _avis = noter(donnees)
    erreur_score = [] if score >= score_mini else [f"score {score} sous le minimum {score_mini}"]
    return not (erreur_champs + erreur_score), erreur_champs + erreur_score


def main() -> int:
    filtre = sys.argv[1] if len(sys.argv) > 1 else ""
    echantillons = sorted(p for p in (RACINE / "echantillons").iterdir() if p.is_dir() and filtre in p.name)
    if not echantillons:
        print("Aucun échantillon à rejouer.")
        return 1

    verts = 0
    for dossier in echantillons:
        ok, erreurs = _jouer_echantillon(dossier)
        if ok:
            verts += 1
            print(f"  OK    {dossier.name}")
        else:
            print(f"  ROUGE {dossier.name}")
            for e in erreurs:
                print(f"        - {e}")
    print(f"\n{verts}/{len(echantillons)} échantillons au vert.")
    return 0 if verts == len(echantillons) else 1


if __name__ == "__main__":
    sys.exit(main())
