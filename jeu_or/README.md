# Jeu d'or NCshift

Le jeu d'or protège l'extraction contre les régressions : un ensemble de
factures (anonymisées ou synthétiques fidèles aux vraies) avec, pour
chacune, les champs attendus. On le rejoue à chaque changement de
l'extracteur.

## Lancer

```bash
pip install -e "backend[dev]"   # une fois, depuis la racine du projet
python jeu_or/evaluer.py       # tout le jeu ; exit 0 = tout vert
python jeu_or/evaluer.py acme  # ne rejoue que les échantillons "acme"
```

## Ajouter un échantillon

1. Créer un dossier `echantillons/<fournisseur>-<cas>/`.
2. Y mettre la facture : `facture.xml` (CII Factur-X) ou `facture.pdf`
   (PDF/A-3 avec XML embarqué). Anonymiser les données clients.
3. Écrire `attendu.json` : les champs que l'extraction doit produire,
   et le score minimum acceptable :

```json
{
  "attendu": {
    "numero": "FA-2026-001",
    "montant_ttc": 240.00,
    "tva_par_taux": [{"taux": 20.0, "base": 200.0, "tva": 40.0}]
  },
  "score_mini": 0.85
}
```

Seuls les champs listés dans `attendu` sont vérifiés : un échantillon peut
sciemment ne contrôler que le champ qui a régressé un jour.

## Règles

- Un échantillon rouge n'est jamais supprimé ni assoupli dans un commit
  d'extraction : on corrige l'extracteur, ou on ajoute l'avis métier qui
  fait descendre le score en dessous de `score_mini` de façon assumée.
- Chaque anomalie fournisseur réelle (générateur Factur-X exotique, TVA
  multiple, escompte...) devient un échantillon.
- Les échantillons ne contiennent jamais de données clients réelles.
