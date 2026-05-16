from httpx_oauth.clients.google import GoogleOAuth2

from klara.config import Settings


def make_google_oauth_client(settings: Settings) -> GoogleOAuth2 | None:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        return None
    return GoogleOAuth2(
        settings.google_oauth_client_id,
        settings.google_oauth_client_secret,
    )
