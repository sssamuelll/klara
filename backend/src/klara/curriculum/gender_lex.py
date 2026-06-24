"""The German gender oracle: parse the open dataset, load it, and resolve a
lemma's gender (exact, then longest-suffix compound) authoritatively."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import GenderLexicon

# genus single-letter code → German definite article.
_GENUS_TO_ARTICLE = {"m": "der", "f": "die", "n": "das"}
# Compound resolution: only trust a known noun as a compound head if it's at
# least this long, to avoid spurious short-suffix matches (e.g. "-ei").
_MIN_COMPOUND_HEAD = 4


@dataclass(frozen=True, slots=True)
class GenderRow:
    lemma: str
    pos: str
    gender: str  # der | die | das


def _find_column(fieldnames: list[str], candidates: set[str]) -> str | None:
    for name in fieldnames:
        if name.strip().lower() in candidates:
            return name
    return None


def _normalize_pos(raw: str | None) -> str:
    """Collapse a CSV pos cell to a short token that fits gender_lexicon.pos
    (varchar(16)). gambolputty's pos is a comma-joined Wiktionary category list
    ("Gebundenes Lexem,Substantiv") that overflows the column; a noun category
    collapses to "noun", anything else to its first category capped at the column
    width. pos is informational only — resolve_gender never reads it."""
    cats = [c.strip() for c in (raw or "").lower().split(",") if c.strip()]
    if not cats or "substantiv" in cats or "noun" in cats:
        return "noun"
    return cats[0][:16]


def parse_gender_csv(text: str) -> list[GenderRow]:
    """Parse the gambolputty/german-nouns CSV. Reads the `lemma` and `genus`
    columns by name (case-insensitive); maps genus m/f/n → der/die/das. Rows
    with empty/unrecognized genus or empty lemma are skipped. Raises if the
    required columns are absent."""
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    lemma_col = _find_column(fields, {"lemma", "wort", "word"})
    genus_col = _find_column(fields, {"genus", "gender", "artikel", "article"})
    if lemma_col is None or genus_col is None:
        raise ValueError(f"CSV must have a lemma and a genus column; got headers: {fields}")
    pos_col = _find_column(fields, {"pos", "wortart"})
    out: list[GenderRow] = []
    seen: set[str] = set()
    for row in reader:
        lemma = (row.get(lemma_col) or "").strip()
        # Bound morphemes (affixes/suffixes: "-algie", "Vor-") are not standalone
        # nouns — keep them out of the oracle.
        if not lemma or lemma.startswith("-") or lemma.endswith("-"):
            continue
        if lemma in seen:
            # gambolputty lists the primary sense first, so the first VALID genus
            # for a lemma wins (der Kaffee, not a later regional das Kaffee).
            continue
        genus = (row.get(genus_col) or "").strip().lower()
        # Accept both genus codes (m/f/n) and full articles (der/die/das), so an
        # article-valued column resolves instead of silently dropping every row.
        article = genus if genus in {"der", "die", "das"} else _GENUS_TO_ARTICLE.get(genus[:1])
        if article is None:
            continue
        seen.add(lemma)
        pos = _normalize_pos(row.get(pos_col)) if pos_col else "noun"
        out.append(GenderRow(lemma=lemma, pos=pos, gender=article))
    return out


async def load_gender_lexicon(db: AsyncSession, *, rows: list[GenderRow]) -> int:
    """Idempotent upsert of the oracle. Returns rows processed."""
    for r in rows:
        stmt = (
            pg_insert(GenderLexicon)
            .values(lemma=r.lemma, pos=r.pos, gender=r.gender)
            .on_conflict_do_update(
                index_elements=["lemma"], set_={"pos": r.pos, "gender": r.gender}
            )
        )
        await db.execute(stmt)
    return len(rows)


async def resolve_gender(db: AsyncSession, lemma: str) -> str | None:
    """Authoritative gender for `lemma`, or None if unknown. Exact match first;
    then the longest known noun that is a suffix of `lemma` (compound head:
    Hausaufgabe → Aufgabe → die). Never guesses."""
    lemma = (lemma or "").strip()
    if not lemma:
        return None
    exact = await db.get(GenderLexicon, lemma)
    if exact is not None:
        return exact.gender
    # Case-insensitive exact fallback (casing drift: a lower-cased input still
    # resolves). Only runs when the fast PK hit missed.
    ci = (
        await db.execute(
            select(GenderLexicon.gender)
            .where(func.lower(GenderLexicon.lemma) == lemma.lower())
            .limit(1)
        )
    ).scalar_one_or_none()
    if ci is not None:
        return ci
    # Compound: the longest lexicon lemma that is a (case-insensitive) suffix of
    # the input and long enough to be a real head (Haus+aufgabe → Aufgabe).
    # ILIKE handles the lower-cased join in compounds. Bounded scan; only runs
    # on exact misses.
    stmt = (
        select(GenderLexicon.gender)
        .where(
            func.length(GenderLexicon.lemma) >= _MIN_COMPOUND_HEAD,
            func.length(GenderLexicon.lemma) < func.length(lemma),
            literal(lemma).ilike(func.concat("%", GenderLexicon.lemma)),
        )
        .order_by(func.length(GenderLexicon.lemma).desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()
