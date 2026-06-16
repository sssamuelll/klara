"""Estado de competencia del usuario, eje léxico, sobre lo que YA existe.

No hay tabla nueva: el known-set son los lemas con UserCard del usuario en el
idioma, canonicalizados. Es la implementación léxica de la interfaz de
competencia; la Rebanada 2 (género) añade otra implementación del mismo contrato.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.lemmatize import canonical_lemma
from klara.models import UserCard, VocabItem, module_vocab
from klara.models.enums import CardState


async def known_set(db: AsyncSession, *, user_id: UUID, language: str) -> set[str]:
    """Lemas canónicos que el usuario ya tiene en SRS para `language`."""
    stmt = (
        select(VocabItem.lemma)
        .join(UserCard, UserCard.vocab_item_id == VocabItem.id)
        .where(UserCard.user_id == user_id, VocabItem.language == language)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {canonical_lemma(lemma, language) for lemma in rows}


# A lexical card is "mastered" once it's in long-term review with a stable
# interval. The advancement gate (PR-B) reads this; the visible panel reads the
# monotonic "encountered" signal instead (PR-A).
MASTERY_INTERVAL_DAYS = 21.0


def is_mastered_lexical(card: UserCard) -> bool:
    """Lexical-axis mastery predicate. Gender (R3) will define its own."""
    return card.state == CardState.REVIEWING and card.interval_days >= MASTERY_INTERVAL_DAYS


async def module_progress(
    db: AsyncSession, *, user_id: UUID, module_id: UUID
) -> tuple[int, int, int]:
    """(encountered, mastered, total) for the module's vocab, in two aggregate
    queries (no N+1). `encountered` = the user has a card; `mastered` =
    is_mastered_lexical. `total` = size of the module's vocab microlist."""
    total = (
        await db.execute(
            select(func.count())
            .select_from(module_vocab)
            .where(module_vocab.c.module_id == module_id)
        )
    ).scalar_one()
    enc_q = (
        select(
            func.count(UserCard.id),
            func.count(UserCard.id).filter(
                and_(
                    UserCard.state == CardState.REVIEWING,
                    UserCard.interval_days >= MASTERY_INTERVAL_DAYS,
                )
            ),
        )
        .select_from(module_vocab)
        .join(
            UserCard,
            and_(
                UserCard.vocab_item_id == module_vocab.c.vocab_item_id,
                UserCard.user_id == user_id,
            ),
        )
        .where(module_vocab.c.module_id == module_id)
    )
    encountered, mastered = (await db.execute(enc_q)).one()
    return int(encountered), int(mastered), int(total)
