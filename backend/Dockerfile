FROM python:3.12-slim

# Utilisateur non privilégié : un conteneur applicatif n'a aucune raison de
# tourner en root.
RUN useradd --create-home --uid 10001 dataguard

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Les dépendances sont installées avant le code : une modification du code ne
# réinvalide alors pas la couche d'installation.
COPY pyproject.toml ./
RUN pip install --no-cache-dir . && rm -rf /root/.cache

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN mkdir -p /app/data/raw && chown -R dataguard:dataguard /app
USER dataguard

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
