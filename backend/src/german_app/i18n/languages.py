from typing import Literal, TypedDict


class LanguageInfo(TypedDict):
    label: str
    speech_locale: str


LanguageCode = Literal["de", "en", "fr", "ja", "pt", "es"]


SUPPORTED_LANGUAGES: dict[str, LanguageInfo] = {
    "de": {"label": "Deutsch", "speech_locale": "de-DE"},
    "en": {"label": "English", "speech_locale": "en-US"},
    "fr": {"label": "Français", "speech_locale": "fr-FR"},
    "ja": {"label": "日本語", "speech_locale": "ja-JP"},
    "pt": {"label": "Português", "speech_locale": "pt-PT"},
    "es": {"label": "Español", "speech_locale": "es-ES"},
}


def validate_language(code: str) -> str:
    if code not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language code '{code}'. Supported: {sorted(SUPPORTED_LANGUAGES)}"
        )
    return code


def language_label(code: str) -> str:
    return SUPPORTED_LANGUAGES.get(code, {"label": code, "speech_locale": code}).get(
        "label", code
    )


def speech_locale(code: str) -> str:
    return SUPPORTED_LANGUAGES.get(code, {"label": code, "speech_locale": code}).get(
        "speech_locale", code
    )
