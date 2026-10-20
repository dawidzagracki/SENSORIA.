"""Stable Polish product slug normalization."""

import re
import unicodedata

SLUG_MAX_LENGTH = 180
_TRANSLITERATION = str.maketrans({"ł": "l", "Ł": "L", "đ": "d", "Đ": "D"})


def slugify(value: str, *, max_length: int = SLUG_MAX_LENGTH) -> str:
    """Convert a name to bounded lowercase ASCII, trimming separator edges."""

    if max_length < 1:
        raise ValueError("Limit sluga musi być dodatni.")
    normalized = unicodedata.normalize("NFKD", value.translate(_TRANSLITERATION))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug[:max_length].rstrip("-")
