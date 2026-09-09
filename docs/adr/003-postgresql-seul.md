# ADR 003 — PostgreSQL seul, sans repli SQLite

## Contexte

Un repli SQLite « pour démarrer sans Docker » avait été envisagé pendant le cadrage.

## Décision

PostgreSQL uniquement, lancé par Docker Compose. Les tests d'API tournent contre une base PostgreSQL de test : conteneur en local, service PostgreSQL dans GitHub Actions.

## Conséquences

Un seul dialecte SQL à connaître, JSONB utilisable pour les détails de contrôles et les configurations, migrations Alembic éprouvées sur la base réelle. Docker devient un prérequis dès le premier démarrage.

Le point décisif est celui des tests : le projet s'appuie sur JSONB et sur des index propres à PostgreSQL, si bien qu'une suite verte sur SQLite ne prouverait rien de ce qui tourne réellement.
