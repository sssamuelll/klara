DEFAULT_LOCALE = "es"
SUPPORTED: set[str] = {"es", "en", "de", "fr", "ja", "pt"}


MESSAGES: dict[str, dict[str, str]] = {
    "errors.languages_must_differ": {
        "es": "El idioma nativo y el idioma a aprender deben ser diferentes.",
        "en": "Your native language and the language you're learning must be different.",
        "de": "Muttersprache und Lernsprache müssen unterschiedlich sein.",
        "fr": "La langue maternelle et la langue à apprendre doivent être différentes.",
        "ja": "母語と学ぶ言語は別のものにしてください。",
        "pt": "A língua materna e a língua a aprender têm de ser diferentes.",
    },
    "errors.vocab_not_found": {
        "es": "Elemento de vocabulario no encontrado",
        "en": "Vocab item not found",
        "de": "Vokabeleintrag nicht gefunden",
        "fr": "Élément de vocabulaire introuvable",
        "ja": "語彙項目が見つかりません",
        "pt": "Item de vocabulário não encontrado",
    },
    "errors.card_not_found": {
        "es": "Tarjeta no encontrada",
        "en": "Card not found",
        "de": "Karte nicht gefunden",
        "fr": "Carte introuvable",
        "ja": "カードが見つかりません",
        "pt": "Cartão não encontrado",
    },
    "errors.story_not_found": {
        "es": "Historia no encontrada",
        "en": "Story not found",
        "de": "Geschichte nicht gefunden",
        "fr": "Histoire introuvable",
        "ja": "物語が見つかりません",
        "pt": "História não encontrada",
    },
    "errors.tts_text_too_long": {
        "es": "Texto demasiado largo (>{max} caracteres)",
        "en": "Text too long (>{max} chars)",
        "de": "Text zu lang (>{max} Zeichen)",
        "fr": "Texte trop long (>{max} caractères)",
        "ja": "テキストが長すぎます({max} 文字超)",
        "pt": "Texto demasiado longo (>{max} caracteres)",
    },
    "errors.tts_provider_unsupported": {
        "es": "Proveedor de TTS no soportado: {provider}",
        "en": "Unsupported TTS provider: {provider}",
        "de": "Nicht unterstützter TTS-Anbieter: {provider}",
        "fr": "Fournisseur TTS non pris en charge : {provider}",
        "ja": "サポートされていない TTS プロバイダー: {provider}",
        "pt": "Fornecedor de TTS não suportado: {provider}",
    },
}


def t(key: str, locale: str, **kwargs: object) -> str:
    bundle = MESSAGES.get(key, {})
    template = bundle.get(locale) or bundle.get(DEFAULT_LOCALE) or key
    return template.format(**kwargs) if kwargs else template
