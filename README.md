# NCshift : de la facture au paiement

Sprint 1 terminé : le socle et l'ingestion. Un fichier entrant est stocké,
horodaté, typé, dédupliqué et tracé ; une facture n'existe qu'à travers sa
machine à états ; chaque changement écrit une ligne d'audit immuable.

## Démarrage rapide

```bash
cp .env.example .env         # remplir IMAP_* ou WATCH_FOLDER au besoin
docker compose up -d --build
# ou, pour développer sans docker :
pip install -e "backend[dev]" && pytest backend/tests -v
uvicorn app.main:app --reload  # depuis backend/
```

La console de démo : http://localhost:8000

Elle montre le livrable de fin de sprint 1 : états des factures, journal
d'audit en temps quasi réel, téléversement de fichiers (simule l'arrivée),
boutons de transition d'état.

## Scénario de démo (critère de done du sprint 1)

1. Déposer via la console : un PDF sale (ex. scan facturier habituel), un
   PDF avec XML Factur-X embarqué, un fichier non facture (image, doc).
2. Montrer que chacun a son type détecté (`pdf`, `pdf_a3_facturx`, `autre`).
3. Déposer le même PDF une seconde fois : `doublon_ignore` dans le journal,
   aucune seconde ligne de facture.
4. Faire avancer une facture d'un état (bouton) et montrer la ligne
   `transition_statut` correspondante dans le journal.
5. `docker compose restart` : rien n'a bougé, tout est persistant (critère
   "redémarrage sans perte").

## Architecture (sprint 1)

```
docker compose
├── api      FastAPI (/healthz, /api/*, console /)   port 8000
├── worker   arq : poll IMAP chaque minute + watcher dossier
├── db        PostgreSQL 16
├── redis     Redis 7 (file arq)
└── volume    fichierdata : fichiers bruts en dev (S3 Scaleway en prod)
```

Pas de serveur S3 local : MinIO a quitté Docker Hub en septembre 2026, et la
démo n'en a pas besoin. Le stockage est derrière le réglage `STOCKAGE` :
`local` (dossier monté, dev), `s3` (Scaleway, prod), `off` (tests). Le code
ne change pas entre les deux.

Le code du backend :

| Module | Rôle |
|---|---|
| `app/models/` | `organisation`, `fichier_source`, `facture`, `fournisseur`, `audit_log` |
| `app/core/states.py` | Machine à états (`recue → … → payee`), transitions validées |
| `app/core/audit.py` | Journal append-only, `changer_statut` = seule porte des transitions |
| `app/ingestion/detect.py` | Type par contenu : PDF, PDF/A-3 Factur-X (XML embarqué), XML UBL/CII |
| `app/ingestion/service.py` | Empreinte SHA-256, dédoublonnage, dépôt du brut, création facture `recue` |
| `app/ingestion/storage.py` | Stockage des fichiers bruts : S3 (prod) ou dossier local (dev) |
| `app/ingestion/imap_poller.py` | Boîte dédiée : lire, ingérer, marquer lu, archiver |
| `app/ingestion/folder_watcher.py` | Dossier partagé : détection, stabilisation, ingestion |
| `app/worker/tasks.py` | arq : cron IMAP + watchdog |
| `app/api/` | Console minimale : lister, journal, transitions (démo) |

## Règles du socle (à ne jamais casser)

- **Aucun fichier n'entre ni ne change d'état sans ligne d'audit.**
  `audit_log` est append-only : aucun update, aucun delete, jamais.
- **Le même contenu deux fois = un doublon ignoré et tracé** (empreinte
  sur le contenu, pas le nom de fichier).
- **Le type se juge sur le contenu**, jamais sur l'extension : le XML
  Factur-X embarqué est le chemin prioritaire de l'extraction (sprint 2).
- **Pas de retour arrière dans la machine à états** : `payee` et
  `rejetee` sont terminaux.

## Empreinte sprint par sprint

- Sprint 2 : interface `Extractor` (XML Factur-X puis OCR+LLM Mistral),
  modèle unifié, score de confiance, jeu d'or.
- Sprint 3 : imports (FEC, virements, balance), référentiel, contrôles n° 1.
- Sprint 4 : app de validation React (rôles, file, PDF à gauche / données à droite).
- Sprint 5 : `ExportAdapter` + SEPA pain.001.
- Sprint 6 : durcissement (HTTPS, sauvegardes, Sentry, RGPD, runbook).

## Secrets

Tout vient de l'environnement (voir `.env.example`). En prod : secrets du
VPS, jamais dans le dépôt, jamais dans l'image. Le graphe image + volumes
est volontairement minimal : un VPS suffit pour ~20 clients.
