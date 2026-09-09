.PHONY: help up down samples demo test lint format migrate openapi clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "};{printf "  %-12s %s\n",$$1,$$2}'

up: ## Démarre base, API et dashboard
	docker compose up --build

down: ## Arrête tout
	docker compose down

samples: ## Régénère les 17 fichiers synthétiques sur l'heure courante
	python3 scripts/generate_samples.py

demo: samples ## Prépare la démonstration (conteneurs déjà démarrés)
	@echo "Fichiers régénérés : la fraîcheur se mesure par rapport à maintenant,"
	@echo "des fichiers datés d'hier fausseraient la démonstration."
	docker compose exec api python -m app.cli seed
	@echo "Reprenez l'identifiant affiché, puis :"
	@echo "  docker compose exec api python -m app.cli run <id> --file data/sample/clean.csv"
	@echo "  docker compose exec api python -m app.cli run <id> --file data/sample/schema_removed.csv"

test: ## Tests backend
	cd backend && python3 -m pytest tests -q

lint: ## Lint backend
	cd backend && python3 -m ruff check app tests alembic

format: ## Formatage backend
	cd backend && python3 -m ruff format app tests alembic

migrate: ## Applique les migrations
	cd backend && python3 -m alembic upgrade head

openapi: ## Exporte le contrat OpenAPI et régénère les types du dashboard
	cd backend && python3 -c "import json;from app.main import create_app;print(json.dumps(create_app().openapi(),ensure_ascii=False,indent=2))" > openapi.json
	cd frontend && npm run generate:api
	@echo "backend/openapi.json et frontend/src/api/schema.d.ts régénérés"

clean: ## Supprime les fichiers bruts téléchargés
	rm -rf data/raw/*
