"""Project 8: i18n API — translations and error explanations."""

from fastapi import APIRouter, Request, Depends
from app.services.i18n_service import t, explain_error, detect_locale, SUPPORTED_LOCALES

router = APIRouter(prefix="/api/i18n", tags=["i18n"])


def get_locale(request: Request) -> str:
    return getattr(request.state, "locale", "en_US")


@router.get("/locales")
def list_locales():
    return list(SUPPORTED_LOCALES)


@router.get("/translate")
def translate(key: str, locale: str = "", loc: str = Depends(get_locale)):
    """Translate a single key. Uses request locale if not specified."""
    loc_final = locale or loc
    return {"key": key, "locale": loc_final, "value": t(key, loc_final)}


@router.get("/translate/batch")
def translate_batch(keys: str, locale: str = "", loc: str = Depends(get_locale)):
    """Translate multiple keys (comma-separated)."""
    loc_final = locale or loc
    key_list = [k.strip() for k in keys.split(",") if k.strip()]
    return {k: t(k, loc_final) for k in key_list}


@router.get("/explain/{error_code}")
def explain(error_code: str, locale: str = "", retry_after: str = "",
            timeout: str = "", loc: str = Depends(get_locale)):
    """Get translated error explanation with causes and solutions."""
    loc_final = locale or loc
    context = {}
    if retry_after:
        context["retry_after"] = retry_after
    if timeout:
        context["timeout"] = timeout
    return explain_error(error_code, loc_final, **context)


@router.get("/detect")
def detect(request: Request):
    """Detect the current request's locale from Accept-Language header."""
    accept_lang = request.headers.get("Accept-Language", "")
    return {
        "accept_language": accept_lang,
        "detected_locale": request.state.locale,
    }
