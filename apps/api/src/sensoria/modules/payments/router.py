"""Payments route namespace; no business endpoints exist yet."""

from fastapi import APIRouter

router = APIRouter(prefix="/payments", tags=["payments"])
