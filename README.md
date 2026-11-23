# NCshift : de la facture au paiement

Sprints 1 et 2 livrés : socle, ingestion, états, audit, puis extraction
Factur-X. Un fichier entrant est stocké, horodaté, typé, dédupliqué et tracé ;
le XML Factur-X (seul ou embarqué dans un PDF/A-3) est extrait exactement,
noté ; une facture dont le score est sous le seuil part en validation
humaine ; chaque changement écrit une ligne d'audit immuable.

## Démarrage rapide

```bash
cp .env.example .env         # remplir IMAP_* ou WATCH_FOLDER au besoin
docker compose up -d --build
# ou, pour développer sans docker :
pip install -e "backend[dev]" && pytest backend/tests -v
uvicorn app.main:app --reload  # depuis backend/
```

La console de démo : http://localhost:8000

Elle montre le livrable de fin de sprint 2 : états des factures avec numéro,
TTC et score de confiance, journal d'audit en temps quasi réel,
téléversement de fichiers (simule l'arrivée, extraction immédiate).

## Scénario de démo (critère de done du sprint 2)

1. Déposer via la console un PDF avec XML Factur-X embarqué (ou un XML CII
   seul) : la facture passe direct en `extraite`, numéro et TTC affichés,
   score 100 %, lignes `extraction` + `transition_statut` au journal.
2. Déposer le même fichier une seconde fois : `doublon_ignore`.
3. Déposer un XML trafiqué (montants incohérents, numéro absent) : la
   facture reste extraite puis part en `a_valider` (`score_faible` au
   journal, avis machine-lisibles).
4. Déposer un PDF sale (scan) : il reste `recue`, aucune extraction
   inventée ; c'est le boulot de l'OCR (sprint 2.5).
5. Redémarrer : rien n'a bougé, tout est persistant.

## Architecture (sprint 2)

```
docker compose
├── api      FastAPI (/healthz, /api/*, console /)   port 8000
├── worker   arq : poll IMAP chaque minute, extraction à +30s, watcher dossier
├── db       PostgreSQL 16
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
| `app/models/` | `organisation`, `fichier_source`, `facture`, `fournisseur`, `audit_log`, `extraction` |
| `app/core/states.py` | Machine à états (`recue → … → payee`), transitions validées |
| `app/core/audit.py` | Journal append-only, `changer_statut` = seule porte des transitions |
| `app/ingestion/detect.py` | Type par contenu : PDF, PDF/A-3 Factur-X (XML embarqué), XML UBL/CII |
| `app/ingestion/service.py` | Empreinte SHA-256, dédoublonnage, dépôt du brut, création facture `recue` |
| `app/ingestion/storage.py` | Stockage des fichiers bruts : S3 (prod) ou dossier local (dev), + relecture |
| `app/ingestion/imap_poller.py` | Boîte dédiée : lire, ingérer, marquer lu, archiver |
| `app/ingestion/folder_watcher.py` | Dossier partagé : détection, stabilisation, ingestion |
| `app/extraction/` | Contrat `Extracteur`, moteur Factur-X (CII), score de confiance, orchestration |
| `app/worker/tasks.py` | arq : cron IMAP + cron extraction + watchdog |
| `app/api/` | Console minimale : lister, journal, transitions, dépôt + extraction (démo) |

Le score de confiance (`SEUIL_CONFIANCE`, 0.85 par défaut) : chaque champ
critique manquant (numéro, date, TTC, vendeur) multiplie le score par 0.55,
une incohérence HT+TVA≠TTC par 0.40, un IBAN dont la clé mod-97 ne passe pas
par 0.50. Sous le seuil, la facture extraite va en `a_valider` : la machine
ne fait jamais semblant d'être sûre.

## Jeu d'or

`jeu_or/` : échantillons de factures avec résultats attendus, rejoués par
`python jeu_or/evaluer.py` (backend installé au préalable). Chaque anomalie
fournisseur réelle devient un échantillon : l'extraction ne régresse jamais
silencieusement.

## Règles du socle (à ne jamais casser)

- **Aucun fichier n'entre ni ne change d'état sans ligne d'audit.**
  `audit_log` est append-only : aucun update, aucun delete, jamais.
- **Le même contenu deux fois = un doublon ignoré et tracé** (empreinte
  sur le contenu, pas le nom de fichier).
- **Le type se juge sur le contenu**, jamais sur l'extension.
- **Aucune donnée inventée à l'extraction** : ce qui n'est pas dans le
  fichier reste à `NULL`, c'est le score qui décide auto ou humain.
- **Pas de retour arrière dans la machine à états** : `payee` et
  `rejetee` sont terminaux.

## Empreinte sprint par sprint

- ~~Sprint 2 : interface `Extractor` (XML Factur-X puis OCR+LLM Mistral),
  modèle unifié, score de confiance, jeu d'or.~~ **Livré.**
- Sprint 2.5 : OCR + LLM Mistral pour les PDF scannés, branché sur le même
  contrat `Extracteur`.
- Sprint 3 : imports (FEC, virements, balance), référentiel, contrôles n° 1.
- Sprint 4 : app de validation React (rôles, file, PDF à gauche / données à droite).
- Sprint 5 : `ExportAdapter` + SEPA pain.001.
- Sprint 6 : durcissement (HTTPS, sauvegardes, Sentry, RGPD, runbook).

## Secrets

Tout vient de l'environnement (voir `.env.example`). En prod : secrets du
VPS, jamais dans le dépôt, jamais dans l'image. Le graphe image + volumes
est volontairement minimal : un VPS suffit pour ~20 clients.
