from datetime import datetime
from enum import Enum
from typing import Annotated, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, mapped_column


def pg_enum(enum_cls: type[Enum], **kwargs: Any) -> SAEnum:
    return SAEnum(
        enum_cls,
        values_callable=lambda obj: [e.value for e in obj],
        **kwargs,
    )

uuid_pk = Annotated[UUID, mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)]
created_ts = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False),
]
updated_ts = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
]


class Base(DeclarativeBase):
    type_annotation_map = {
        UUID: PGUUID(as_uuid=True),
    }
