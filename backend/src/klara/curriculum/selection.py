"""Selección del próximo objetivo léxico = (corpus por frecuencia) - (known-set),
filtrado a palabras de contenido y a la banda del nivel del usuario.

Esto INVIERTE la dirección de control: el LLM recibe estos lemas como objetivo y
redacta la historia alrededor; deja de improvisar la secuencia (spec §6).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.competence import known_set
from klara.curriculum.lemmatize import canonical_lemma
from klara.models import VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech

# Palabras de contenido: el eje léxico drillea sustantivos/verbos/adj/adv. Las
# function words de altísima frecuencia (der/die/das/und/ist) NO entran aquí —
# der/die/das es el eje de GÉNERO (Rebanada 2), no un ítem léxico (spec D4).
CONTENT_POS = (
    PartOfSpeech.NOUN,
    PartOfSpeech.VERB,
    PartOfSpeech.ADJECTIVE,
    PartOfSpeech.ADVERB,
)

# Orden CEFR para la compuerta de banda (cefr_level <= user.level).
CEFR_ORDER: dict[CEFRLevel, int] = {
    CEFRLevel.A0: 0,
    CEFRLevel.A1: 1,
    CEFRLevel.A2: 2,
    CEFRLevel.B1: 3,
    CEFRLevel.B2: 4,
    CEFRLevel.C1: 5,
}


async def next_target_words(
    db: AsyncSession, *, user_id: UUID, language: str, level: CEFRLevel, n: int = 5
) -> list[VocabItem]:
    """Próximos `n` lemas de contenido por frecuencia, en banda, no sabidos."""
    known = await known_set(db, user_id=user_id, language=language)
    ceiling = CEFR_ORDER[level]
    allowed = [lvl for lvl, order in CEFR_ORDER.items() if order <= ceiling]
    stmt = (
        select(VocabItem)
        .where(
            VocabItem.language == language,
            VocabItem.pos.in_(CONTENT_POS),
            VocabItem.cefr_level.in_(allowed),
            VocabItem.frequency_rank.is_not(None),
        )
        .order_by(VocabItem.frequency_rank.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    # El cut por known-set es en memoria (igual que practice_queue): el inventario
    # por usuario está acotado y no se puede restar un set en SQL sin acoplar.
    out: list[VocabItem] = []
    for v in rows:
        if canonical_lemma(v.lemma, language) in known:
            continue
        out.append(v)
        if len(out) >= n:
            break
    return out
