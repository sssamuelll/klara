# backend/src/klara/services/practice_session.py
"""Cierre del ciclo SRS por pronunciación — canal de MANTENIMIENTO.

Recibe el resultado de una sesión de Practice (por línea: la UserCard que la
respalda, la palabra-foco, la frase dicha y las bandas por token). Por cada
carta DUE del usuario, deriva la banda de la palabra-foco, la mapea a un rating
(conservador, nunca Easy) y la reprograma con el scheduler de mantenimiento
(escalera corta, sin promover). Una transacción atómica. Dedup por card_id.

NO modifica srs_engine.schedule_next_review (canal de recall, futuro). NO acepta
target_language del cliente: la carta se resuelve por id + ownership.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import Review, UserCard
from klara.models.enums import ReviewRating
from klara.schemas.srs import PronunciationReviewIn, RescheduledCardOut
from klara.services.srs_engine import schedule_pronunciation_maintenance
from klara.services.tokens import word_tokens_by_index, worst_band

# Mapeo conservador banda->rating. NUNCA Easy: la promoción es del canal de
# recall, no de la articulación. Distinto de BAND_RANK (eso ordena bandas).
_BAND_TO_RATING: dict[str, ReviewRating] = {
    "bad": ReviewRating.AGAIN,
    "ok": ReviewRating.HARD,
    "good": ReviewRating.GOOD,
}


def _focus_band(sentence_target: str, focus_text: str, word_bands: dict[int, str]) -> str | None:
    """Banda de la palabra-foco; fallback a la peor banda de la frase (spec D3).

    Re-tokeniza con el tokenizador canónico (mismos índices que el frontend) y
    busca el token == focus_text. Si esa palabra no tiene banda (Azure la omitió,
    o el foco no está en la frase), cae a la peor banda — lo más conservador.
    """
    target = focus_text.casefold()
    for idx, word in word_tokens_by_index(sentence_target).items():
        if word.casefold() == target:
            band = word_bands.get(idx)
            if band is not None:
                return band
            break
    return worst_band(word_bands)


def _is_due(next_review_at: datetime | None, now: datetime) -> bool:
    """Mismo predicado que routers/srs.due_cards: NULL o <= now."""
    if next_review_at is None:
        return True
    if next_review_at.tzinfo is None:
        next_review_at = next_review_at.replace(tzinfo=UTC)
    return next_review_at <= now


async def apply_pronunciation_reviews(
    db: AsyncSession,
    *,
    user_id: UUID,
    reviews: list[PronunciationReviewIn],
) -> list[RescheduledCardOut]:
    now = datetime.now(UTC)
    seen: set[UUID] = set()
    out: list[RescheduledCardOut] = []

    for r in reviews:
        if r.card_id in seen:  # dedup intra-request (idempotencia sin lock)
            continue
        seen.add(r.card_id)

        card = await db.get(UserCard, r.card_id)
        # Invariante de seguridad: la carta resuelta por un id del cliente DEBE
        # pertenecer al usuario. Es la única barrera de aislamiento (spec §4.3).
        if card is None or card.user_id != user_id:
            continue
        if not _is_due(card.next_review_at, now):
            continue

        band = _focus_band(r.sentence_target, r.focus_text, r.word_bands)
        if band is None:
            continue

        prev_interval = card.interval_days
        interval, next_at = schedule_pronunciation_maintenance(card, band)
        card.interval_days = interval
        card.next_review_at = next_at
        card.last_reviewed_at = now
        db.add(
            Review(
                user_card_id=card.id,
                user_id=user_id,
                rating=_BAND_TO_RATING[band],
                prev_interval_days=prev_interval,
                new_interval_days=interval,
            )
        )
        out.append(
            RescheduledCardOut(
                focus_text=r.focus_text, interval_days=interval, next_review_at=next_at
            )
        )

    await db.commit()
    return out
