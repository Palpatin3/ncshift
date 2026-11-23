# Spec : que se passe-t-il quand un fichier arrive ?

Périmètre : sprints 1 et 2 (ingestion + extraction Factur-X). Chaque
comportement décrit ici est celui du code livré et vérifié par les tests
pytest (`backend/tests/`) ; cette spec est la référence pour les démos,
le pilotage et le sprint 2.5 (OCR), qui s'y branchera sans rien casser.

## 1. Le pipeline en une image

```mermaid
flowchart TD
    A["Arrivée du fichier<br/>(console / mail IMAP / dossier partagé)"] --> B{"Déjà reçu ?<br/>(empreinte SHA-256 du contenu)"}
    B -- "oui" --> C["audit `doublon_ignore`<br/>aucune nouvelle ligne, STOP"]
    B -- "non" --> D["Détection du type<br/>sur le CONTENU (jamais l'extension)"]
    D --> E["Dépôt du brut<br/>(volume local dev / S3 prod)<br/>fichier_source + audit `fichier_recu`"]
    E --> F{"Type facture possible ?<br/>(pdf, pdf_a3_facturx, xml)"}
    F -- "non (autre)" --> G["Pas de ligne facture.<br/>FIN : tracé au journal seulement."]
    F -- "oui" --> H["Facture créée `recue`<br/>+ audit `recue`"]
    H --> I["Extraction<br/>(console : immédiate ;<br/>worker : chaque minute à +30 s)"]
    I -- "aucun moteur" --> J["reste `recue`<br/>(OCR au sprint 2.5)"]
    I -- "échec" --> K["ligne extraction échouée<br/>+ audit `extraction_echouee`,<br/>reste `recue`"]
    I -- "réussite" --> L["score + avis,<br/>données copiées sur la facture,<br/>audit `extraction`<br/>transition vers `extraite`"]
    L --> M{"score >= SEUIL_CONFIANCE<br/>(0.85 par défaut) ?"}
    M -- "non" --> N["audit `score_faible`<br/>transition vers `a_valider`<br/>(file humaine)"]
    M -- "oui" --> O["`extraite` : la suite de<br/>la machine à états (contrôles, etc.)"]
```

Règle transversale : **aucune étape ne lève d'exception vers l'appelant**.
Un fichier pourri est un cas normal, pas une panne : il est typé, tracé et
oublié. Le commit de chaque étape appartient à l'appelant (console ou worker).

## 2. Détection du type (sur le contenu, jamais l'extension)

| Test contenu | Type détecté |
|---|---|
| En-tête `%PDF` + pièce jointe nommée `factur-x*`, `zugferd*` ou `*.xml` | `pdf_a3_facturx` |
| En-tête `%PDF` sans XML embarqué repéré (ou pièce jointe sans marqueur) | `pdf` |
| XML dont la racine (hors namespace) est `CrossIndustryInvoice` **ou** `Invoice` | `xml` |
| XML mal formé, ou tout le reste (PNG, DOCX, ZIP...) | `autre` |

Un PDF illisible par pypdf reste `pdf` (pas un crash) ; un XML illisible
reste `autre`. La détection ne lève jamais.

## 3. Comportement attendu par format

### 3.1 XML Factur-X CII seul (pièce jointe d'un mail, dépôt console)

- Type `xml`, facture créée `recue`.
- Extraction `facturx_xml` : parsing par noms locaux, insensible aux
  namespaces du générateur (rsm/ram/udt peu importe).
- Champs extraits : numéro, date facture, date échéance, devise, nom
  vendeur, SIREN (schemeID 0002, SIRET 14 → 9), TVA vendeur, IBAN payé,
  lignes de TVA par taux, HT, total TVA, TTC.
- Aucun champ inventé : ce qui n'est pas dans le fichier reste `NULL`.
- Score 1.0 si tout est cohérent → statut `extraite`.
- Événements audit (ordre) : `fichier_recu`, `recue`, `extraction`,
  `transition_statut` (recue → extraite).

### 3.2 PDF/A-3 avec XML Factur-X embarqué

Identique à 3.1 ; la seule différence : l'extracteur relit le XML dans
les pièces jointes du PDF (même recherche de marqueur que la détection).
Type `pdf_a3_facturx`. C'est **le chemin roi** : exact et gratuit.

### 3.3 XML UBL (racine `Invoice`)

- Type `xml` (la détection ne distingue pas encore UBL de CII) : facture
  créée `recue` — présent dans les mails de certains fournisseurs.
- L'extracteur sprint 2 ne parse que le CII : échec **tracé**, pas
  silencieux : ligne `extraction` échouée (`format_non_supporte:Invoice`),
  audit `extraction_echouee`, la facture **reste `recue`**.
- Attendu : le support UBL (ou le rejeu OCR) ferme ce cas sans changer le
  pipeline.

### 3.4 PDF classique, scan, ou PDF/A-3 sans XML repéré

- Type `pdf`, facture créée `recue`.
- Aucun moteur d'extraction au sprint 2 : le dépôt console répond
  `extraction: null`, le worker ne la sélectionne pas.
- La facture **reste `recue`** : rien n'est inventé, ni numéro, ni montant.
- Attendu : sprint 2.5 (OCR + LLM Mistral) branché sur le même contrat
  `Extracteur` ; le seul changement visible sera le statut.

### 3.5 Autre (image, doc, XML non facture...)

- Type `autre` : ligne `fichier_source` + audit `fichier_recu`,
  **aucune ligne facture**. C'est voulu : la table des factures ne doit
  contenir que des candidates.

### 3.6 Doublon (tout format confondu)

- Empreinte SHA-256 du **contenu** (le nom ne compte pas) déjà connue
  pour l'organisation → `doublon_ignore` au journal, fichier existant
  conservé tel quel, aucune nouvelle ligne nulle part, STOP.

## 4. Notation et routage

Score de départ 1.0, pénalités multiplicatives :

| Contrôle | Pénalité | Avis |
|---|---|---|
| Champ critique manquant (numéro, date, TTC, vendeur) | ×0.55 chacun | `champ_manquant:<champ>` |
| HT + TVA ≠ TTC (tolérance 0.02) | ×0.40 | `incoherence_montants` |
| IBAN dont la clé mod-97 échoue (ISO 13616) | ×0.50 | `iban_invalide` |

- Score >= `SEUIL_CONFIANCE` (0.85) → `extraite` : la machine est sûre.
- Score < seuil → audit `score_faible` puis transition vers `a_valider` :
  les doutes vont à l'humain, avec toutes les données extraites visibles.
- Chaque tentative (réussie ou non) écrit une ligne `extraction`
  append-only : données, avis, score. Rien n'est écrasé.

## 5. Qui déclenche quoi, quand

| Déclencheur | Quand | Rôle |
|---|---|---|
| Console (`POST /api/fichiers`) | au dépôt | ingestion + extraction immédiate, réponse avec score/statut |
| Worker `poll_imap` | chaque minute, à :00 | lecture boîte dédiée, ingestion |
| Worker `extraire_file` | chaque minute, à :30 | extraction des `recue` de type `xml`/`pdf_a3_facturx` |
| Watcher dossier | événement stabilisé | ingestion |

Le tour du worker rattrape tout ce que la console a déjà traité : une
facture `extraite` n'est plus `recue`, elle est naturellement ignorée.

## 6. Critères d'acceptation d'une démo (sprint 2)

1. PDF Factur-X réel déposé → `extraite`, numéro/TTC/score affichés,
   journal : `extraction` + `transition_statut`.
2. Même fichier re-déposé → `doublon_ignore`, pas de nouvelle facture.
3. XML avec TTC modifié (incohérent) → `a_valider`, journal : `extraction`,
   `transition_statut`, `score_faible`, `transition_statut`.
4. Scan sale → reste `recue`, aucun champ inventé.
5. PNG → journal seulement, pas dans la table des factures.
6. Redémarrage de la stack → tout est toujours là (persistance).

Le jeu d'or (`jeu_or/evaluer.py`) rejoue ces garanties sur des échantillons
de référence à chaque évolution de l'extracteur : une régression ne passe
jamais silencieusement.
