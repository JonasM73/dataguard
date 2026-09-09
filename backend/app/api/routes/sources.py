"""Endpoints des sources."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import SourceCreate, SourceOut
from app.db.models import Source

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=list[SourceOut])
def list_sources(session: Session = Depends(get_db)) -> list[Source]:
    return list(session.execute(select(Source).order_by(Source.created_at.desc())).scalars().all())


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, session: Session = Depends(get_db)) -> Source:
    source = Source(**payload.model_dump())
    session.add(source)
    session.flush()
    return source
