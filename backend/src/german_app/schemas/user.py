from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from german_app.i18n import SUPPORTED_LANGUAGES
from german_app.models.enums import CEFRLevel


def _validate_lang(code: str | None) -> str | None:
    if code is None:
        return None
    if code not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language '{code}'. Supported: {sorted(SUPPORTED_LANGUAGES)}"
        )
    return code


class UserOut(BaseModel):
    id: UUID
    display_name: str
    level: CEFRLevel
    native_language: str
    target_language: str
    learning_context: str | None = None


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    level: CEFRLevel | None = None
    native_language: str | None = None
    target_language: str | None = None
    learning_context: str | None = None

    @field_validator("native_language", "target_language")
    @classmethod
    def _check_language(cls, v: str | None) -> str | None:
        return _validate_lang(v)

    @model_validator(mode="after")
    def _check_distinct(self) -> "UserUpdate":
        if (
            self.native_language is not None
            and self.target_language is not None
            and self.native_language == self.target_language
        ):
            raise ValueError("native_language and target_language must be different")
        return self
