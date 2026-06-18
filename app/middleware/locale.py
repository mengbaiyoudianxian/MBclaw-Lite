"""Middleware: detect locale from Accept-Language header and inject into request state."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.i18n_service import detect_locale


class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        accept_lang = request.headers.get("Accept-Language", "")
        request.state.locale = detect_locale(accept_lang)
        response = await call_next(request)
        return response
