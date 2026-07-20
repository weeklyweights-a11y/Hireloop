from fastapi import APIRouter, Query

from src.services import meta as meta_service

router = APIRouter(tags=["meta"])


@router.get("/meta/locations")
def meta_locations(q: str | None = Query(default=None)) -> dict:
    return {"suggestions": meta_service.suggest_locations(q)}


@router.get("/meta/roles")
def meta_roles(q: str | None = Query(default=None)) -> dict:
    return {"suggestions": meta_service.suggest_roles(q)}
