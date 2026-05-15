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
    "auth.allowlist_blocked": {
        "es": "Este correo no está autorizado para registrarse.",
        "en": "This email is not authorized to sign up.",
        "de": "Diese E-Mail ist nicht für die Registrierung freigeschaltet.",
        "fr": "Cet e-mail n'est pas autorisé à s'inscrire.",
        "ja": "このメールアドレスは登録を許可されていません。",
        "pt": "Este email não está autorizado a registar-se.",
    },
    "auth.invalid_credentials": {
        "es": "Correo o contraseña incorrectos.",
        "en": "Invalid email or password.",
        "de": "E-Mail oder Passwort ungültig.",
        "fr": "E-mail ou mot de passe invalide.",
        "ja": "メールアドレスまたはパスワードが正しくありません。",
        "pt": "Email ou palavra-passe inválidos.",
    },
    "auth.email_not_verified": {
        "es": "Tenés que verificar tu correo antes de continuar.",
        "en": "Please verify your email before continuing.",
        "de": "Bitte bestätige deine E-Mail, bevor du fortfährst.",
        "fr": "Veuillez vérifier votre e-mail avant de continuer.",
        "ja": "続行する前にメールアドレスを確認してください。",
        "pt": "Verifica o teu email antes de continuar.",
    },
    "auth.token_expired": {
        "es": "El enlace expiró. Pedí uno nuevo.",
        "en": "This link has expired. Request a new one.",
        "de": "Dieser Link ist abgelaufen. Fordere einen neuen an.",
        "fr": "Ce lien a expiré. Demandez-en un nouveau.",
        "ja": "このリンクは期限切れです。新しいリンクをリクエストしてください。",
        "pt": "Este link expirou. Pede um novo.",
    },
    "auth.email.verify_subject": {
        "es": "Confirmá tu correo en Klara",
        "en": "Confirm your email on Klara",
        "de": "Bestätige deine E-Mail bei Klara",
        "fr": "Confirmez votre e-mail sur Klara",
        "ja": "Klaraでメールアドレスを確認してください",
        "pt": "Confirma o teu email no Klara",
    },
    "auth.email.verify_body_html": {
        "es": "<p>Hola,</p><p>Confirmá tu correo para empezar a usar Klara:</p><p><a href=\"{link}\">Confirmar correo</a></p><p>Si no fuiste vos, ignorá este mensaje.</p>",
        "en": "<p>Hi,</p><p>Confirm your email to start using Klara:</p><p><a href=\"{link}\">Confirm email</a></p><p>If this wasn't you, ignore this message.</p>",
        "de": "<p>Hallo,</p><p>Bestätige deine E-Mail, um Klara zu nutzen:</p><p><a href=\"{link}\">E-Mail bestätigen</a></p><p>Wenn du das nicht warst, ignoriere diese Nachricht.</p>",
        "fr": "<p>Bonjour,</p><p>Confirmez votre e-mail pour commencer à utiliser Klara :</p><p><a href=\"{link}\">Confirmer l'e-mail</a></p><p>Si ce n'était pas vous, ignorez ce message.</p>",
        "ja": "<p>こんにちは、</p><p>Klaraを使い始めるためにメールアドレスを確認してください：</p><p><a href=\"{link}\">メールを確認</a></p><p>心当たりがない場合はこのメッセージを無視してください。</p>",  # noqa: RUF001
        "pt": "<p>Olá,</p><p>Confirma o teu email para começar a usar o Klara:</p><p><a href=\"{link}\">Confirmar email</a></p><p>Se não foste tu, ignora esta mensagem.</p>",
    },
    "auth.email.reset_subject": {
        "es": "Restablecer tu contraseña de Klara",
        "en": "Reset your Klara password",
        "de": "Setze dein Klara-Passwort zurück",
        "fr": "Réinitialiser votre mot de passe Klara",
        "ja": "Klaraのパスワードをリセット",
        "pt": "Repor a tua palavra-passe do Klara",
    },
    "auth.email.reset_body_html": {
        "es": "<p>Hola,</p><p>Hacé clic para crear una contraseña nueva:</p><p><a href=\"{link}\">Cambiar contraseña</a></p><p>El enlace vence en una hora. Si no fuiste vos, ignorá este mensaje.</p>",
        "en": "<p>Hi,</p><p>Click to set a new password:</p><p><a href=\"{link}\">Reset password</a></p><p>The link expires in an hour. If this wasn't you, ignore this message.</p>",
        "de": "<p>Hallo,</p><p>Klicke, um ein neues Passwort zu setzen:</p><p><a href=\"{link}\">Passwort zurücksetzen</a></p><p>Der Link läuft in einer Stunde ab. Wenn du das nicht warst, ignoriere diese Nachricht.</p>",
        "fr": "<p>Bonjour,</p><p>Cliquez pour définir un nouveau mot de passe :</p><p><a href=\"{link}\">Réinitialiser le mot de passe</a></p><p>Le lien expire dans une heure. Si ce n'était pas vous, ignorez ce message.</p>",
        "ja": "<p>こんにちは、</p><p>クリックして新しいパスワードを設定してください：</p><p><a href=\"{link}\">パスワードをリセット</a></p><p>リンクは1時間後に期限切れになります。心当たりがない場合は無視してください。</p>",  # noqa: RUF001
        "pt": "<p>Olá,</p><p>Clica para definir uma nova palavra-passe:</p><p><a href=\"{link}\">Repor palavra-passe</a></p><p>O link expira em uma hora. Se não foste tu, ignora esta mensagem.</p>",
    },
}


def t(key: str, locale: str, **kwargs: object) -> str:
    bundle = MESSAGES.get(key, {})
    template = bundle.get(locale) or bundle.get(DEFAULT_LOCALE) or key
    return template.format(**kwargs) if kwargs else template
