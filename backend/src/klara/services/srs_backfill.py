"""Backfill de estado FSRS (#125) — sync a propósito.

Replay-ea el ledger `reviews` (mezclado recall+pronunciation histórico —
indistinguible pre-#125; se mide en el análisis del dump) vía
Scheduler.reschedule_card para llenar SOLO las 4 columnas FSRS de UserCard.
JAMÁS toca state/interval_days/next_review_at: transición gradual, default de
fsrs4anki — FSRS toma el mando en la próxima review de cada carta, cero shock
en la cola de due. `reviews.channel` existe justo para que esto no vuelva a
pasar (el Optimizer v2 entrena solo con recall).

Sync a propósito: la migración de Alembic lo llama con Session(bind=op.get_bind())
y los tests con AsyncSession.run_sync — una sola implementación para ambos.

Lock: dentro de la migración, el ACCESS EXCLUSIVE del ALTER TABLE se sostiene
durante TODO el replay (misma transacción). Con el ledger actual (0 filas en
prod, medido en el dump 2026-08-07) es ~ms; si algún día el ledger crece a
miles de filas, mover el backfill fuera de la migración (script) o batchear.
"""

from fsrs import Card, ReviewLog
from sqlalchemy import select
from sqlalchemy.orm import Session

from klara.models import Review, UserCard
from klara.services.srs_engine import _RATING_MAP, _utc, get_scheduler


def backfill_fsrs_state(session: Session) -> int:
    """Replay del ledger para toda carta sin stability. Idempotente: las cartas
    ya-backfilled no se re-tocan. Devuelve el número de cartas actualizadas.
    Hace flush pero JAMÁS commit — el caller es dueño de la transacción."""
    cards = session.scalars(select(UserCard).where(UserCard.stability.is_(None))).all()
    updated = 0
    for card in cards:
        rows = session.scalars(
            select(Review).where(Review.user_card_id == card.id).order_by(Review.reviewed_at.asc())
        ).all()
        if not rows:
            continue  # sin historial no se inventa memoria
        logs = [
            ReviewLog(
                card_id=1,
                rating=_RATING_MAP[r.rating],
                review_datetime=_utc(r.reviewed_at),
                review_duration=r.elapsed_seconds,
            )
            for r in rows
        ]
        replayed = get_scheduler().reschedule_card(Card(card_id=1), logs)
        card.stability = replayed.stability
        card.difficulty = replayed.difficulty
        card.fsrs_step = replayed.step
        card.fsrs_last_review = replayed.last_review
        updated += 1
    session.flush()
    return updated
