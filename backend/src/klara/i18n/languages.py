from typing import Literal, TypedDict


class LanguageInfo(TypedDict):
    label: str
    speech_locale: str


LanguageCode = Literal["de", "en", "fr", "ja", "pt", "es"]


# Keep in sync with frontend/src/lib/languages.ts (and bump both together when
# adding/removing a code). The /api/v1/me/languages endpoint exposes this so
# the frontend *could* fetch it, but today it just mirrors the constants.
# Speech locales target Latin American Spanish and Brazilian Portuguese rather
# than the European variants. Azure's es-ES expects ceceo (`/θ/` for c/z) and
# pt-PT expects European Portuguese phonology — both produce systematic
# false-low scores for LatAm/BR speakers reciting correctly pronounced words.
SUPPORTED_LANGUAGES: dict[str, LanguageInfo] = {
    "de": {"label": "Deutsch", "speech_locale": "de-DE"},
    "en": {"label": "English", "speech_locale": "en-US"},
    "fr": {"label": "Français", "speech_locale": "fr-FR"},
    "ja": {"label": "日本語", "speech_locale": "ja-JP"},
    "pt": {"label": "Português", "speech_locale": "pt-BR"},
    "es": {"label": "Español", "speech_locale": "es-MX"},
}


def validate_language(code: str) -> str:
    if code not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language code '{code}'. Supported: {sorted(SUPPORTED_LANGUAGES)}"
        )
    return code


def language_label(code: str) -> str:
    info = SUPPORTED_LANGUAGES.get(code)
    return info["label"] if info else code


def speech_locale(code: str) -> str:
    info = SUPPORTED_LANGUAGES.get(code)
    return info["speech_locale"] if info else code
