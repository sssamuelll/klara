"""El taller (F0): tarjetas de repaso de tema libre, aisladas del alemán.

Mismo motor FSRS que `/srs`, pero tablas propias (`study_cards`,
`study_card_reviews`) que nunca tocan las del alemán (`user_cards`,
`vocab_items`). Todos los handlers usan `TallerUser` (no `CurrentUser`): fuera
de la allowlist, 403.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import Text, func, select

from klara.dependencies import DBSession, LocaleDep, TallerUser
from klara.i18n import t
from klara.models import StudyCard, StudyCardReview
from klara.schemas.taller import (
    BulkCreateIn,
    BulkOut,
    CardCreateIn,
    CardListOut,
    OverviewOut,
    ReviewIn,
    StudyCardOut,
)
from klara.services.srs_engine import apply_review, project_intervals

router = APIRouter(prefix="/taller", tags=["taller"])


def _card_to_out(card: StudyCard) -> StudyCardOut:
    return StudyCardOut(
        id=card.id,
        front=card.front,
        back=card.back,
        tags=card.tags,
        batch_id=card.batch_id,
        archived_at=card.archived_at,
        state=card.state,
        interval_days=card.interval_days,
        next_review_at=card.next_review_at,
        last_reviewed_at=card.last_reviewed_at,
        repetitions=card.repetitions,
        next_intervals=project_intervals(card),
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


@router.get("/overview", response_model=OverviewOut)
async def overview(db: DBSession, user: TallerUser) -> OverviewOut:
    now = datetime.now(UTC)
    active = (StudyCard.user_id == user.id, StudyCard.archived_at.is_(None))
    total = (
        await db.execute(select(func.count()).select_from(StudyCard).where(*active))
    ).scalar_one()
    due = (
        await db.execute(
            select(func.count())
            .select_from(StudyCard)
            .where(*active, StudyCard.next_review_at <= now)
        )
    ).scalar_one()
    tag_expr = func.unnest(StudyCard.tags, type_=Text).label("tag")
    rows = (
        await db.execute(
            select(tag_expr, func.count().label("count"))
            .where(*active)
            .group_by(tag_expr)
            .order_by(tag_expr.asc())
        )
    ).all()
    return OverviewOut(
        total=total,
        due=due,
        tags=[{"tag": row.tag, "count": row.count} for row in rows],
    )


@router.post("/cards", response_model=StudyCardOut, status_code=status.HTTP_201_CREATED)
async def create_card(payload: CardCreateIn, db: DBSession, user: TallerUser) -> StudyCardOut:
    card = StudyCard(
        user_id=user.id,
        front=payload.front,
        back=payload.back,
        tags=payload.tags,
        batch_id=payload.batch_id,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return _card_to_out(card)


@router.post("/cards/bulk", response_model=BulkOut, status_code=status.HTTP_201_CREATED)
async def create_bulk(payload: BulkCreateIn, db: DBSession, user: TallerUser) -> BulkOut:
    stmt = (
        select(StudyCard)
        .where(StudyCard.user_id == user.id, StudyCard.batch_id == payload.batch_id)
        .order_by(StudyCard.created_at.asc(), StudyCard.id.asc())
    )
    existing = (await db.execute(stmt)).scalars().all()
    if not existing:
        # Replay idempotente por (user_id, batch_id): si ya hay filas, se
        # devuelven tal cual, sin insertar nada nuevo.
        db.add_all(
            [
                StudyCard(
                    user_id=user.id,
                    front=item.front,
                    back=item.back,
                    tags=payload.tags,
                    batch_id=payload.batch_id,
                )
                for item in payload.cards
            ]
        )
        await db.commit()
        existing = (await db.execute(stmt)).scalars().all()
    return BulkOut(created=len(existing), cards=[_card_to_out(card) for card in existing])


@router.get("/cards", response_model=CardListOut)
async def list_cards(
    db: DBSession,
    user: TallerUser,
    tag: str | None = None,
    limit: int = Query(50, ge=1),
    offset: int = Query(0, ge=0),
) -> CardListOut:
    filters = [StudyCard.user_id == user.id, StudyCard.archived_at.is_(None)]
    if tag is not None:
        filters.append(StudyCard.tags.any(tag))
    total = (
        await db.execute(select(func.count()).select_from(StudyCard).where(*filters))
    ).scalar_one()
    rows = (
        (
            await db.execute(
                select(StudyCard)
                .where(*filters)
                .order_by(StudyCard.created_at.asc(), StudyCard.id.asc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return CardListOut(total=total, items=[_card_to_out(card) for card in rows])


@router.get("/cards/due", response_model=list[StudyCardOut])
async def due_cards(
    db: DBSession,
    user: TallerUser,
    limit: int = Query(20, ge=1),
) -> list[StudyCardOut]:
    # Sin `le`: el contrato es CAPEAR a 50 en silencio, no rechazar con 422.
    effective_limit = min(limit, 50)
    now = datetime.now(UTC)
    rows = (
        (
            await db.execute(
                select(StudyCard)
                .where(
                    StudyCard.user_id == user.id,
                    StudyCard.archived_at.is_(None),
                    StudyCard.next_review_at <= now,
                )
                .order_by(StudyCard.next_review_at.asc())
                .limit(effective_limit)
            )
        )
        .scalars()
        .all()
    )
    return [_card_to_out(card) for card in rows]


@router.post("/cards/{card_id}/review", response_model=StudyCardOut)
async def submit_review(
    card_id: UUID,
    payload: ReviewIn,
    db: DBSession,
    user: TallerUser,
    locale: LocaleDep,
) -> StudyCardOut:
    card = await db.get(StudyCard, card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(status_code=404, detail=t("errors.card_not_found", locale))

    # apply_review calcula Y escribe el nuevo estado FSRS en `card`; devuelve el
    # interval_days ANTERIOR, que es lo que el ledger guarda como prev.
    prev_interval_days = apply_review(card, payload.rating)

    review = StudyCardReview(
        user_id=user.id,
        study_card_id=card.id,
        rating=payload.rating,
        elapsed_seconds=payload.elapsed_seconds,
        prev_interval_days=prev_interval_days,
        new_interval_days=card.interval_days,
        device=payload.device,
    )
    db.add(review)
    await db.commit()
    await db.refresh(card)
    return _card_to_out(card)


@router.post("/cards/{card_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_card(
    card_id: UUID,
    db: DBSession,
    user: TallerUser,
    locale: LocaleDep,
) -> None:
    card = await db.get(StudyCard, card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(status_code=404, detail=t("errors.card_not_found", locale))
    card.archived_at = datetime.now(UTC)
    await db.commit()


@router.get("/export")
async def export_cards(db: DBSession, user: TallerUser) -> Response:
    rows = (
        (
            await db.execute(
                select(StudyCard)
                .where(StudyCard.user_id == user.id)
                .order_by(StudyCard.created_at.asc(), StudyCard.id.asc())
            )
        )
        .scalars()
        .all()
    )
    lines = [
        "\t".join(
            [
                card.front,
                card.back,
                ",".join(card.tags),
                card.created_at.isoformat(),
                "true" if card.archived_at is not None else "false",
            ]
        )
        for card in rows
    ]
    return Response(content="\n".join(lines), media_type="text/tab-separated-values")
