"""Vouchers route namespace; no business endpoints exist yet."""

from fastapi import APIRouter

router = APIRouter(prefix="/vouchers", tags=["vouchers"])
