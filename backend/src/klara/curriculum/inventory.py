"""Carga del inventario de referencia (eje léxico) desde una lista curada externa.

El rank y la banda CEFR vienen de una fuente CURADA (Kelly / SUBTLEX-DE + CEFR),
NUNCA del LLM. Upsert por (lema en CASO NATURAL, idioma, pos): puebla frequency_rank
y SOBREESCRIBE cefr_level (el inferido por LLM en story_gen es ruido, no verdad de
terreno). Idempotente. El lema se almacena TAL CUAL lo da la lista (caso natural,
p.ej. "Haus" capitalizado) — NO se minusculiza: canonical_lemma re-lematizaría un
sustantivo en minúsculas como verbo ("haus"→"hausen"). La agrupación por familia se
hace al LEER (known-set/cobertura aplican canonical_lemma para la clave de comparación);
story_gen también almacena el lema en caso natural, así que el upsert casa por igual.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


@dataclass(frozen=True, slots=True)
class FrequencyRow:
    lemma: str
    pos: PartOfSpeech
    cefr_level: CEFRLevel
    frequency_rank: int


def parse_frequency_tsv(text: str) -> list[FrequencyRow]:
    """Parsea un TSV `lemma<TAB>pos<TAB>cefr<TAB>rank` (con cabecera)."""
    out: list[FrequencyRow] = []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines[1:], start=2):  # salta la cabecera
        cols = [c.strip() for c in ln.split("\t")]
        if len(cols) != 4:
            raise ValueError(f"TSV malformado en línea {i}: se esperaban 4 columnas")
        lemma, pos, cefr, rank = cols
        if not lemma:
            raise ValueError(f"TSV malformado en línea {i}: lemma vacío")
        out.append(
            FrequencyRow(
                lemma=lemma,
                pos=PartOfSpeech(pos.lower()),
                cefr_level=CEFRLevel(cefr.upper()),
                frequency_rank=int(rank),
            )
        )
    return out


async def load_frequency(db: AsyncSession, *, language: str, rows: list[FrequencyRow]) -> int:
    """Upsertea el inventario. Devuelve cuántas filas se procesaron. Idempotente."""
    for r in rows:
        lemma = r.lemma.strip()  # caso natural — NO minusculizar (ver docstring)
        stmt = (
            pg_insert(VocabItem)
            .values(
                lemma=lemma,
                language=language,
                pos=r.pos,
                frequency_rank=r.frequency_rank,
                cefr_level=r.cefr_level,
            )
            .on_conflict_do_update(
                constraint="uq_vocab_lemma_lang_pos",
                set_={
                    "frequency_rank": r.frequency_rank,
                    "cefr_level": r.cefr_level,
                },
            )
        )
        await db.execute(stmt)
    await db.commit()
    # El upsert escribe vía SQL crudo y sortea el identity-map del ORM. Con
    # expire_on_commit=False (config de la sesión), un VocabItem ya cargado en la
    # sesión seguiría mostrando su frequency_rank/cefr_level viejos al releerlo.
    # Expiramos para que cualquier lector en la MISMA sesión vea la fila fresca.
    db.expire_all()
    return len(rows)
