from fastapi_users_db_sqlalchemy import SQLAlchemyBaseOAuthAccountTableUUID

from german_app.models.base import Base


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    __tablename__ = "oauth_accounts"
