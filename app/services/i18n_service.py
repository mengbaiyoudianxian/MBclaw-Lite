"""Project 8: Internationalization — multi-language support + error explainer.

Language detection: Accept-Language header → select best match
Translation: key.path → localized string with format interpolation
Error explainer: error code → translated description + causes + solutions
"""

import json
import os
from typing import Any

I18N_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "i18n")
SUPPORTED_LOCALES = {"zh_CN", "en_US", "ja_JP"}
FALLBACK_LOCALE = "en_US"

_cache: dict[str, dict] = {}


def load_locale(locale: str) -> dict:
    if locale in _cache:
        return _cache[locale]
    path = os.path.join(I18N_DIR, f"{locale}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _cache[locale] = data
    return data


def detect_locale(accept_language: str | None) -> str:
    """Parse Accept-Language header → best match."""
    if not accept_language:
        return FALLBACK_LOCALE

    # Parse: "zh-CN,zh;q=0.9,en;q=0.8"
    locales = accept_language.replace(" ", "").split(",")
    for loc in locales:
        if ";" in loc:
            loc = loc.split(";")[0]
        # Normalize: zh-CN → zh_CN
        normalized = loc.replace("-", "_")
        if normalized in SUPPORTED_LOCALES:
            return normalized
        # Try primary language only
        primary = normalized.split("_")[0]
        for sl in SUPPORTED_LOCALES:
            if sl.startswith(primary):
                return sl

    return FALLBACK_LOCALE


def t(path: str, locale: str = FALLBACK_LOCALE, **kwargs) -> str:
    """Translate a key path. Example: t('errors.404', 'zh_CN') → '未找到'."""
    data = load_locale(locale)
    if not data:
        data = load_locale(FALLBACK_LOCALE)

    keys = path.split(".")
    val: Any = data
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k, "")
        else:
            return path
    if isinstance(val, str) and kwargs:
        val = val.format(**kwargs)
    return val if isinstance(val, str) else path


def explain_error(error_code: str, locale: str = FALLBACK_LOCALE,
                  **context) -> dict:
    """Get translated error explanation with causes and solutions.

    Returns structured explanation: {title, detail, causes, solutions}
    """
    title = t(f"errors.{error_code}", locale)
    detail = t(f"errors.{error_code}_detail", locale, **context)

    # Common causes and solutions per error code
    causes_map = {
        "404": ["资源已被删除或重命名", "URL 拼写错误", "ID 不存在"],
        "400": ["缺少必填字段", "字段类型不匹配", "参数值超出范围"],
        "500": ["代码逻辑错误", "外部服务不可用", "文件系统错误"],
        "401": ["API Key 过期", "Key 格式错误", "未配置认证"],
        "403": ["权限不足", "资源不属于当前项目", "操作被安全策略禁止"],
        "429": ["短时间内请求过多", "未实现请求节流", "并发任务过多"],
        "rate_limit": ["免费额度用尽", "并发数超限", "每分钟请求数超限"],
        "db_error": ["数据库文件损坏", "磁盘空间不足", "并发写入冲突"],
        "file_error": ["路径不存在", "权限不足", "磁盘已满"],
        "llm_timeout": ["网络连接不稳定", "模型服务过载", "请求 token 过多"],
    }

    solutions_map = {
        "404": "确认 ID 是否正确，或刷新列表查看可用资源。",
        "400": "查阅 API 文档，确认所有必填字段和格式。",
        "500": "查看服务器日志获取详细错误信息，稍后重试。",
        "401": "在设置页面重新配置 API Key。",
        "403": "确认项目归属，或联系项目管理员授予权限。",
        "429": "等待 {retry_after} 秒后重试，或降低请求频率。",
        "rate_limit": "降低请求频率，使用批量 API 合并请求，或升级套餐。",
        "db_error": "检查数据库文件路径和权限，必要时从备份恢复。",
        "file_error": "检查磁盘空间（df -h），确认目录权限（ls -la）。",
        "llm_timeout": "检查网络连接，降低请求 token 数，或切换模型。",
    }

    causes = causes_map.get(error_code, ["未知原因"])
    solutions = solutions_map.get(error_code, "请联系管理员获取帮助。").format(**context) if isinstance(solutions_map.get(error_code, ""), str) and "{" in solutions_map.get(error_code, "") else solutions_map.get(error_code, "请联系管理员获取帮助。")

    return {
        "error_code": error_code,
        "title": title,
        "detail": detail,
        "causes": causes,
        "solutions": solutions,
        "locale": locale,
    }
