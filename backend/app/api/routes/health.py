"""Endpoint de santé : API et base."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="État de l'API et de la base")
def health(session: Session = Depends(get_db)) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
        database = "up"
    except Exception:
        # La santé se rapporte, elle ne lève pas : un 500 ici priverait
        # l'appelant de l'information qu'il venait chercher.
        database = "down"
    return {"status": "ok" if database == "up" else "degraded", "database": database}
