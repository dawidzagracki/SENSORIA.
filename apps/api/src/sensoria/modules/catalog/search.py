"""PostgreSQL full-text query construction and privacy-minimal query analytics."""

from __future__ import annotations

import unicodedata

from sqlalchemy import cast, func, literal, literal_column
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.sql.elements import ColumnElement

from .models import Product


def normalize_query(value: str | None) -> str | None:
    """Collapse whitespace and case-fold for cache identity and popularity grouping."""

    if value is None:
        return None
    text = canonical_query(value)
    if text is None:
        return None
    text = text.replace("ł", "l")
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )[:160]
    return normalized or None


def canonical_query(value: str | None) -> str | None:
    """Normalize spaces and case while retaining diacritics for rank-sensitive cache keys."""

    if value is None:
        return None
    text = " ".join(value.split()).casefold()
    return text or None


def search_predicate(query: str) -> ColumnElement[bool]:
    """Match accent-preserving and folded Polish morphological lexeme channels."""

    accented_config = cast(literal("public.sensoria_polish"), REGCONFIG)
    folded_config = cast(literal("public.sensoria_polish_unaccented"), REGCONFIG)
    accented_query = func.plainto_tsquery(accented_config, query)
    folded_query = func.plainto_tsquery(
        folded_config,
        func.unaccent(literal_column("'public.unaccent'::regdictionary"), query),
    )
    return Product.search_vector.op("@@")(accented_query) | Product.search_vector_unaccented.op(
        "@@"
    )(folded_query)


def search_rank(query: str) -> ColumnElement[float]:
    """Rank title (A) above short/category (B) and full description (C) matches."""

    accented_config = cast(literal("public.sensoria_polish"), REGCONFIG)
    folded_config = cast(literal("public.sensoria_polish_unaccented"), REGCONFIG)
    accented_query = func.plainto_tsquery(accented_config, query)
    folded_query = func.plainto_tsquery(
        folded_config,
        func.unaccent(literal_column("'public.unaccent'::regdictionary"), query),
    )
    return func.ts_rank_cd(Product.search_vector, accented_query) + (
        func.ts_rank_cd(Product.search_vector_unaccented, folded_query) * 0.25
    )
