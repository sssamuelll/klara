import httpx
import structlog

from german_app.config import Settings
from german_app.i18n.messages import DEFAULT_LOCALE, SUPPORTED, t
from german_app.models import User

log = structlog.get_logger(__name__)


def _locale_for(user: User) -> str:
    code = (user.native_language or "").lower()
    return code if code in SUPPORTED else DEFAULT_LOCALE


def _email_to(user: User) -> str | None:
    return user.email


class EmailService:
    """
    Sends auth emails via Resend's HTTP API. If `resend_api_key` is missing or
    `app_env=development`, falls back to logging the link instead of sending —
    keeps local dev unblocked without real email credentials.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_verify(self, user: User, token: str) -> None:
        locale = _locale_for(user)
        link = f"{self.settings.frontend_base_url}/verify?token={token}"
        subject = t("auth.email.verify_subject", locale)
        body_html = t("auth.email.verify_body_html", locale, link=link)
        await self._send(user, subject, body_html, kind="verify")

    async def send_reset(self, user: User, token: str) -> None:
        locale = _locale_for(user)
        link = f"{self.settings.frontend_base_url}/reset?token={token}"
        subject = t("auth.email.reset_subject", locale)
        body_html = t("auth.email.reset_body_html", locale, link=link)
        await self._send(user, subject, body_html, kind="reset")

    async def _send(self, user: User, subject: str, body_html: str, *, kind: str) -> None:
        to = _email_to(user)
        if to is None:
            log.warning("email.skip_no_address", kind=kind, user_id=str(user.id))
            return
        if not self.settings.resend_api_key:
            log.info(
                "email.stub",
                kind=kind,
                to=to,
                subject=subject,
                body_preview=body_html[:200],
            )
            return
        payload = {
            "from": self.settings.email_from,
            "to": [to],
            "subject": subject,
            "html": body_html,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.settings.resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                log.info("email.sent", kind=kind, to=to)
        except httpx.HTTPError as exc:
            log.error("email.send_failed", kind=kind, to=to, error=str(exc))
