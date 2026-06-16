"""Active-module helpers: the read/write of the user's curriculum position, the
module's target lemmas (fed to generation), and auto-enrollment of module vocab
into the SRS (the "heat source" — reading produces SRS state)."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import Module, User, UserCard, VocabItem, module_vocab


async def read_active_module(db: AsyncSession, user: User) -> Module | None:
    """Read-only: the user's active module, or None. Never writes (used by GET)."""
    if user.current_module_id is None:
        return None
    return await db.get(Module, user.current_module_id)


async def ensure_active_module(db: AsyncSession, user: User) -> Module | None:
    """Write path: if the user has no active module and modules exist for their
    target language, set it to the lowest sequence_order and persist. The single
    canonical initialization point (called from create_story)."""
    if user.current_module_id is not None:
        return await db.get(Module, user.current_module_id)
    stmt = (
        select(Module)
        .where(Module.language == user.target_language)
        .order_by(Module.sequence_order.asc())
        .limit(1)
    )
    first = (await db.execute(stmt)).scalar_one_or_none()
    if first is None:
        return None
    user.current_module_id = first.id
    await db.flush()
    return first


async def module_target_lemmas(db: AsyncSession, module: Module) -> list[str]:
    stmt = (
        select(VocabItem.lemma)
        .join(module_vocab, module_vocab.c.vocab_item_id == VocabItem.id)
        .where(module_vocab.c.module_id == module.id)
    )
    return list((await db.execute(stmt)).scalars().all())


async def module_vocab_ids(db: AsyncSession, module: Module) -> set[UUID]:
    stmt = select(module_vocab.c.vocab_item_id).where(module_vocab.c.module_id == module.id)
    return set((await db.execute(stmt)).scalars().all())


async def enroll_cards(db: AsyncSession, *, user_id: UUID, vocab_item_ids: list[UUID]) -> None:
    """Idempotently create NEW SRS cards for the given vocab items. Reuses the
    unique constraint to skip words the user already has. Caller commits."""
    if not vocab_item_ids:
        return
    # Explicit id per row: UserCard.id has a Python-side default (uuid4) only —
    # supply it so the insert can never emit a NULL id regardless of how the
    # multi-row VALUES form treats client-side defaults.
    stmt = (
        pg_insert(UserCard)
        .values(
            [
                {"id": uuid4(), "user_id": user_id, "vocab_item_id": vid}
                for vid in vocab_item_ids
            ]
        )
        .on_conflict_do_nothing(constraint="uq_user_card_user_vocab")
    )
    await db.execute(stmt)
