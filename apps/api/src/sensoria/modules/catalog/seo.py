"""Derived SEO values; null database fields deliberately mean automatic values."""

import re
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in {"script", "style"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def plain_description(value: str | None, *, fallback: str, limit: int = 160) -> str:
    """Strip markup, normalize whitespace, and cut at a word boundary."""

    parser = _TextExtractor()
    parser.feed(value or "")
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip() or fallback
    if len(text) <= limit:
        return text
    boundary = text[:limit].rsplit(" ", 1)[0]
    return boundary if boundary else text


def product_meta_title(name: str, manual: str | None) -> str:
    return manual.strip() if manual and manual.strip() else name


def product_meta_description(
    name: str, short_description: str | None, description: str | None, manual: str | None
) -> str:
    if manual and manual.strip():
        return plain_description(manual, fallback=f"Poznaj produkt: {name}.")
    source = short_description or description
    return plain_description(source, fallback=f"Poznaj produkt: {name}.")


def category_meta_description(name: str, description: str | None, manual: str | None) -> str:
    if manual and manual.strip():
        return plain_description(manual, fallback=f"Poznaj kategorię: {name}.")
    return plain_description(description, fallback=f"Poznaj kategorię: {name}.")


def decimal_price(grosze: int) -> str:
    """Format integer grosz as an exact decimal string, without floating point."""

    sign = "-" if grosze < 0 else ""
    amount = abs(grosze)
    return f"{sign}{amount // 100}.{amount % 100:02d}"
