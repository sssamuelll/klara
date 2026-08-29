"""Rate limit in-memory por IP, compartido por waitlist y login.

ponytail: por proceso (un worker en prod; se resetea al reiniciar) y single-hop
X-Forwarded-For (confía en el último hop si el peer inmediato es el proxy del
host). El dict se purga de ventanas expiradas al pasar de 1024 IPs distintas,
así la rotación de IPv6 no crece sin límite. Si hay N workers, cadena de proxies
o abuso real: slowapi con forwarded-allow-ips.
"""

from __future__ import annotations

import ipaddress
import time

from fastapi import HTTPException, Request, status

from klara.i18n.messages import DEFAULT_LOCALE, t

_MAX_HITS_ENTRIES = 1024


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    xff = request.headers.get("x-forwarded-for")
    if not xff:
        return peer
    try:
        peer_addr = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if not (peer_addr.is_loopback or peer_addr.is_private):
        return peer
    candidate = xff.split(",")[-1].strip()
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return peer
    return candidate


class RateLimiter:
    def __init__(self, window_s: int, max_per_window: int) -> None:
        self.window_s = window_s
        self.max_per_window = max_per_window
        self._hits: dict[str, tuple[int, float]] = {}

    def reset(self) -> None:
        self._hits.clear()

    def clear(self, ip: str) -> None:
        """Borra el cupo de esta IP (login exitoso). No-op si no tenía entrada."""
        self._hits.pop(ip, None)

    def hit(self, ip: str, now: float | None = None) -> bool:
        """Registra una petición; True si con ella se excede el cupo."""
        t = now if now is not None else time.monotonic()
        if len(self._hits) > _MAX_HITS_ENTRIES:
            expired = [k for k, (_, start) in self._hits.items() if t - start > self.window_s]
            for k in expired:
                del self._hits[k]
        count, start = self._hits.get(ip, (0, t))
        if t - start > self.window_s:
            count, start = 0, t
        count += 1
        self._hits[ip] = (count, start)
        return count > self.max_per_window


waitlist_limiter = RateLimiter(window_s=3600, max_per_window=10)
# Spec android §2.5: 10 intentos / 5 min por IP sobre las tres rutas de login.
login_limiter = RateLimiter(window_s=300, max_per_window=10)

_LOGIN_PATHS = ("/auth/jwt/login", "/auth/bearer/login", "/auth/google/native")


def login_rate_limit(request: Request) -> None:
    """Dependencia de router: los routers de auth traen también /logout, y ese
    no cuenta — solo se limita lo que adivina contraseñas o tokens."""
    if not request.url.path.endswith(_LOGIN_PATHS):
        return
    if login_limiter.hit(client_ip(request)):
        # getattr en vez de klara.dependencies.get_locale: ese módulo importa
        # klara.auth.manager, que importa este módulo (on_after_login) — un
        # import directo acá cerraría el ciclo.
        locale = getattr(request.state, "locale", DEFAULT_LOCALE)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=t("auth.too_many_attempts", locale),
            headers={"Retry-After": str(login_limiter.window_s)},
        )
