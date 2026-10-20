"""Stable duplicate detection shared by manual and imported customer addresses."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def address_fingerprint(address_type: str, snapshot: dict[str, Any]) -> str:
    """Hash only delivery identity fields, excluding labels and volatile point metadata."""
    if address_type == "parcel_locker":
        canonical: dict[str, str] = {
            "code": _normalized(snapshot.get("code"), upper=True),
        }
    else:
        canonical = {
            "street": _normalized(snapshot.get("street")),
            "postal_code": _normalized(snapshot.get("postal_code")),
            "city": _normalized(snapshot.get("city")),
            "country": _normalized(snapshot.get("country") or "PL").upper(),
        }
    payload = json.dumps(
        {"type": address_type, "address": canonical},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _normalized(value: Any, *, upper: bool = False) -> str:
    result = " ".join(value.split()).casefold() if isinstance(value, str) else ""
    return result.upper() if upper else result
