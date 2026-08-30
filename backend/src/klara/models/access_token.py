from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTableUUID
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    """Sesión Bearer del app nativo (spec android §2.1).

    Una fila = una sesión revocable: el logout borra la fila y el token muere
    de verdad — a diferencia del JWT del cookie, que vive 30 días pase lo que pase.
    """

    __tablename__ = "access_tokens"

    # Igual que OAuthAccount: la clase base apunta a "user.id"; la tabla es "users".
    user_id: Mapped[GUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
    )
