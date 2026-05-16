from fastapi_users_db_sqlalchemy import SQLAlchemyBaseOAuthAccountTableUUID

from klara.models.base import Base


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    __tablename__ = "oauth_accounts"
