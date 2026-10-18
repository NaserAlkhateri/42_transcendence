"""HTTP hardening applied to every API response (NA-06). Caddy (BU-02) terminates TLS and should send the same
headers for the frontend's static files; see doc/SECURITY.md."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import error_body


def install_security(app: FastAPI) -> None:
    @app.middleware("http")
    async def harden(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        settings = get_settings()
        length = request.headers.get("content-length")
        if length is not None and length.isdigit() and int(length) > settings.max_request_bytes:
            return JSONResponse(
                status_code=413, content=error_body("payload_too_large", "The request body is too large.")
            )

        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("Referrer-Policy", "same-origin")
        headers.setdefault("X-Frame-Options", "DENY")
        if headers.get("content-type", "").startswith("application/json"):
            # JSON answers are data, never pages: nothing may run, load or frame them. Swagger pages and the
            # PDF report keep their own behaviour (X-Frame-Options still stops framing).
            headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if request.url.path.startswith("/api/"):
            headers.setdefault("Cache-Control", "no-store")  # personal data must not sit in shared caches
        if settings.cookie_secure:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
