"""Convert the Debian Polish Hunspell dictionary into PostgreSQL Ispell files."""

from pathlib import Path
import unicodedata


def ascii_form(value: str) -> str:
    """Remove Polish diacritics while retaining the dictionary's affix rules."""

    value = value.replace("ł", "l").replace("Ł", "L")
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


source = Path("/usr/share/hunspell")
target = Path("/out")
target.mkdir(parents=True, exist_ok=True)

for extension in ("aff", "dic"):
    content = (source / f"pl_PL.{extension}").read_bytes().decode("iso-8859-2")
    if extension == "aff":
        content = content.replace("SET ISO8859-2", "SET UTF-8", 1)
    (target / f"sensoria_pl.{('affix' if extension == 'aff' else 'dict')}").write_text(
        content, encoding="utf-8", newline="\n"
    )
    (target / f"sensoria_pl_folded.{('affix' if extension == 'aff' else 'dict')}").write_text(
        ascii_form(content), encoding="utf-8", newline="\n"
    )
