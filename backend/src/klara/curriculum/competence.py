"""Estado de competencia del usuario, eje léxico, sobre lo que YA existe.

No hay tabla nueva: el known-set son los lemas con UserCard del usuario en el
idioma, canonicalizados. Es la implementación léxica de la interfaz de
competencia; la Rebanada 2 (género) añade otra implementación del mismo contrato.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.lemmatize import canonical_lemma
from klara.models import UserCard, VocabItem


async def known_set(db: AsyncSession, *, user_id: UUID, language: str) -> set[str]:
    """Lemas canónicos que el usuario ya tiene en SRS para `language`."""
    stmt = (
        select(VocabItem.lemma)
        .join(UserCard, UserCard.vocab_item_id == VocabItem.id)
        .where(UserCard.user_id == user_id, VocabItem.language == language)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {canonical_lemma(lemma, language) for lemma in rows}
