"""Active-module helpers: the read/write of the user's curriculum position, the
module's target lemmas (fed to generation), and auto-enrollment of module vocab
into the SRS (the "heat source" — reading produces SRS state)."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import Module, User, UserCard, VocabItem, module_vocab
from klara.models.enums import CEFRLevel, PartOfSpeech


async def read_active_module(db: AsyncSession, user: User) -> Module | None:
    """Read-only: the user's active module, or None. Never writes (used by GET)."""
    if user.current_module_id is None:
        return None
    module = await db.get(Module, user.current_module_id)
    # Guard against a stale pointer after the user changed target_language —
    # a module in the wrong language would feed mismatched lemmas to generation.
    if module is None or module.language != user.target_language:
        return None
    return module


async def ensure_active_module(db: AsyncSession, user: User) -> Module | None:
    """Write path: if the user has no active module and modules exist for their
    target language, set it to the lowest sequence_order and persist. The single
    canonical initialization point (called from create_story)."""
    if user.current_module_id is not None:
        current = await db.get(Module, user.current_module_id)
        if current is not None and current.language == user.target_language:
            return current
        # Stale (language changed or module gone) — clear and reinitialize below.
        user.current_module_id = None
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
            [{"id": uuid4(), "user_id": user_id, "vocab_item_id": vid} for vid in vocab_item_ids]
        )
        .on_conflict_do_nothing(constraint="uq_user_card_user_vocab")
    )
    await db.execute(stmt)


async def load_modules(db: AsyncSession, *, language: str, modules: list[dict]) -> int:
    """Idempotently seed curriculum modules + their vocab for a language.
    Upserts VocabItems on (lemma, language, pos), modules on (language,
    sequence_order), and links them in module_vocab. Returns module count."""
    for spec in modules:
        # Upsert the module (idempotent on language + sequence_order).
        mod_stmt = (
            pg_insert(Module)
            .values(
                language=language,
                cefr_level=CEFRLevel(spec["cefr_level"]),
                sequence_order=spec["sequence_order"],
                title=spec["title"],
                can_dos=spec.get("can_dos", []),
                grammatical_focus=spec.get("grammatical_focus", []),
            )
            .on_conflict_do_update(
                constraint="uq_module_lang_seq",
                set_={
                    "cefr_level": CEFRLevel(spec["cefr_level"]),
                    "title": spec["title"],
                    "can_dos": spec.get("can_dos", []),
                    "grammatical_focus": spec.get("grammatical_focus", []),
                },
            )
            .returning(Module.id)
        )
        module_id = (await db.execute(mod_stmt)).scalar_one()

        # Replace the module's vocab links (idempotent re-seed must not leave
        # stale links when the curated list changes). Safe: UserCards reference
        # vocab_items directly, not these association rows.
        await db.execute(delete(module_vocab).where(module_vocab.c.module_id == module_id))

        for w in spec["vocab"]:
            voc_stmt = (
                pg_insert(VocabItem)
                .values(
                    lemma=w["lemma"],
                    language=language,
                    pos=PartOfSpeech(w.get("pos", "noun")),
                    gender=w.get("gender"),
                    translations=w.get("translations", {}),
                )
                .on_conflict_do_update(
                    constraint="uq_vocab_lemma_lang_pos",
                    set_={
                        "gender": w.get("gender"),
                        "translations": w.get("translations", {}),
                    },
                )
                .returning(VocabItem.id)
            )
            vocab_id = (await db.execute(voc_stmt)).scalar_one()
            link_stmt = (
                pg_insert(module_vocab)
                .values(module_id=module_id, vocab_item_id=vocab_id)
                .on_conflict_do_nothing()
            )
            await db.execute(link_stmt)
    return len(modules)
