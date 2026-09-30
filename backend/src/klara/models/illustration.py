from sqlalchemy import Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, uuid_pk


class Illustration(Base):
    """Portada de una historia: una imagen por escena (spec 2026-09-30 §3.2).

    `hash` = sha256("{style_version}|{escena normalizada}"). El modelo se guarda
    pero no entra en la clave: si cambiamos de modelo, las imágenes ya hechas
    siguen sirviendo."""

    __tablename__ = "illustrations"

    id: Mapped[uuid_pk]
    hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scene: Mapped[str] = mapped_column(Text, nullable=False)
    style_version: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(40), nullable=False)
    image_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[created_ts]
