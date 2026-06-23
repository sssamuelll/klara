"""Estado de competencia del usuario, eje léxico, sobre lo que YA existe.

No hay tabla nueva: el known-set son los lemas con UserCard del usuario en el
idioma, canonicalizados. Es la implementación léxica de la interfaz de
competencia; la Rebanada 2 (género) añade otra implementación del mismo contrato.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.gender_eligibility import gender_eligible_clause
from klara.curriculum.lemmatize import canonical_lemma
from klara.models import GenderAttempt, UserCard, VocabItem, module_vocab
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


# Gender-axis mastery (R3). The competence interface's gender implementation,
# sibling of is_mastered_lexical. Mastery is read off historical GenderAttempt
# evidence (the frozen was_correct), never re-graded. Display-only (never gates).
GENDER_MASTERY_STREAK_N = 3


def _streak_mastered(attempts_desc: list, n: int) -> bool:
    """Pure: mastered iff there are at least n attempts and the most recent n
    (attempts_desc[0] is newest) are all correct. The single source of truth for
    the streak rule — both per-noun and per-module paths call it."""
    return len(attempts_desc) >= n and all(a.was_correct for a in attempts_desc[:n])


async def is_mastered_gender(db: AsyncSession, *, user_id: UUID, vocab_item_id: UUID) -> bool:
    """Per-noun gender mastery: the most recent GENDER_MASTERY_STREAK_N attempts
    for this (user, noun) are all correct. Deterministic order via
    (attempted_at DESC, id DESC)."""
    rows = (
        (
            await db.execute(
                select(GenderAttempt)
                .where(
                    GenderAttempt.user_id == user_id,
                    GenderAttempt.vocab_item_id == vocab_item_id,
                )
                .order_by(GenderAttempt.attempted_at.desc(), GenderAttempt.id.desc())
                .limit(GENDER_MASTERY_STREAK_N)
            )
        )
        .scalars()
        .all()
    )
    return _streak_mastered(list(rows), GENDER_MASTERY_STREAK_N)


async def module_gender_progress(
    db: AsyncSession, *, user_id: UUID, module_id: UUID
) -> tuple[int, int, int]:
    """(gender_encountered, gender_mastered, gender_total) for the module's
    gender-gradable nouns — the parallel of module_progress for the gender axis.
    Eligible = de + oracle + NOUN + gender in der/die/das (same predicate as
    build_gender_cloze). Two queries, no N+1; bucket the globally-ordered
    attempts in Python and apply the shared _streak_mastered."""
    eligible = (
        (
            await db.execute(
                select(VocabItem.id)
                .select_from(module_vocab)
                .join(VocabItem, VocabItem.id == module_vocab.c.vocab_item_id)
                .where(
                    module_vocab.c.module_id == module_id,
                    *gender_eligible_clause(),
                )
            )
        )
        .scalars()
        .all()
    )
    total = len(eligible)
    if total == 0:
        return (0, 0, 0)
    rows = (
        (
            await db.execute(
                select(GenderAttempt)
                .where(
                    GenderAttempt.user_id == user_id,
                    GenderAttempt.vocab_item_id.in_(eligible),
                )
                .order_by(GenderAttempt.attempted_at.desc(), GenderAttempt.id.desc())
            )
        )
        .scalars()
        .all()
    )
    by_noun: dict[UUID, list] = {}
    for r in rows:
        by_noun.setdefault(r.vocab_item_id, []).append(r)
    encountered = len(by_noun)
    mastered = sum(
        1 for attempts in by_noun.values() if _streak_mastered(attempts, GENDER_MASTERY_STREAK_N)
    )
    return (encountered, mastered, total)
