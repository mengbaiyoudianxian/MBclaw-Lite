import json
import os

_locale_data: dict[str, dict] = {}
I18N_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "i18n")


def _load(lang: str):
    path = os.path.join(I18N_DIR, f"{lang}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            _locale_data[lang] = json.load(f)


def t(key: str, lang: str = "zh_CN") -> str:
    if lang not in _locale_data:
        _load(lang)
    return _locale_data.get(lang, {}).get(key, key)


def get_message(key: str, lang: str = "zh_CN") -> str:
    return t(key, lang)
