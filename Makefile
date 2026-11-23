.PHONY: install test up down logs console

install:  ## installe le backend en mode éditable + outils de test
	pip install -e "backend[dev]"

test:     ## lance les tests du sprint 1 (SQLite en mémoire, aucune infra requise)
	pytest backend/tests -v

up:        ## démarre le stack complet (api + worker + postgres + redis + minio)
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api worker

console:  ## ouvre la console de démo
	open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000
