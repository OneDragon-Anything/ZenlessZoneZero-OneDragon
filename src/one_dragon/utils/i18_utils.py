import gettext
import locale
import logging
import os
from collections.abc import Callable
from typing import Any

from one_dragon.utils import os_utils

LANGUAGES: dict[str, str] = {
    'zh-CN': '简体中文',
    'en': 'English',
    'vi': 'Tiếng Việt',
}

_LANGUAGE_ALIASES: dict[str, str] = {
    'zh': 'zh-CN',
    'zh_cn': 'zh-CN',
    'zh-cn': 'zh-CN',
    'zh-hans': 'zh-CN',
    'zh-hans-cn': 'zh-CN',
    'en_us': 'en',
    'en-us': 'en',
    'en_gb': 'en',
    'en-gb': 'en',
    'vi_vn': 'vi',
    'vi-vn': 'vi',
}

_gt: dict[str, dict[str, gettext.GNUTranslations | None]] = {}
_default_lang = 'zh-CN'
_language_changed_callbacks: list[Callable[[str], None]] = []
_log = logging.getLogger(__name__)
_SEMANTIC_MSGIDS: dict[str, str] = {
    'app.settings': '设置',
    'settings.language': '界面语言',
    'settings.appearance': '外观',
    'settings.game': '游戏设置',
    'settings.script_environment': '脚本环境',
    'settings.notifications': '通知设置',
    'settings.custom': '自定义设置',
    'common.ok': '确定',
    'common.cancel': '取消',
    'common.confirm': '确认',
    'common.save': '保存',
    'common.delete': '删除',
    'common.reset': '重置',
}


def normalize_language(language: str | None) -> str:
    """Normalize an operating-system locale or legacy config value."""
    if not language:
        return 'en'
    normalized = language.replace('_', '-').lower()
    if normalized in LANGUAGES:
        return normalized
    return _LANGUAGE_ALIASES.get(normalized, 'en')


def detect_language() -> str:
    """Detect the operating-system language."""
    try:
        system_locale = locale.getdefaultlocale()[0]
        if system_locale:
            return normalize_language(system_locale)
    except (ValueError, TypeError):
        pass
    return 'en'


def detect_and_set_default_language():
    """Detect and apply the operating-system language."""
    return update_default_lang(detect_language())

def get_translations(model: str, lang: str) -> gettext.GNUTranslations | None:
    """Load a gettext catalog for a logical message model."""
    translate_path = os_utils.get_resource_path('assets', 'text', 'output')
    gettext_lang = 'zh' if lang == 'zh-CN' else lang
    lang_dir = os.path.join(translate_path, gettext_lang, 'LC_MESSAGES', f'{model}.mo')
    # Return None when the catalog is not bundled.
    if not os.path.exists(lang_dir):
        return None
    gettext.bindtextdomain(model, translate_path)
    return gettext.translation(model, localedir=translate_path, languages=[gettext_lang])


def gt(
    msg: str | None,
    model: str = 'ui',
    lang: str | None = None,
    **kwargs: Any,
) -> str:
    """Return localized text and format named arguments when supplied.

    Existing code uses Chinese source text as gettext msgids, so this function
    keeps that calling convention while new code can migrate incrementally.
    """
    if msg is None or len(msg) == 0:
        return ''
    lang = normalize_language(lang or _default_lang)
    if lang is None:
        lang = _default_lang
    if model not in _gt:
        _gt[model] = {}
    if lang not in _gt[model]:
        _gt[model][lang] = get_translations(model, lang)

    trans = _gt[model][lang]
    text = trans.gettext(msg) if trans is not None else msg
    if text == msg and lang not in ('en', 'zh-CN'):
        fallback = _gt.setdefault(model, {}).get('en')
        if fallback is None:
            fallback = get_translations(model, 'en')
            _gt[model]['en'] = fallback
        if fallback is not None:
            text = fallback.gettext(msg)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            _log.warning('Unable to format translated text %s', msg, exc_info=True)
    return text


def tr(key: str, model: str = 'ui', language: str | None = None, **kwargs: Any) -> str:
    """Semantic alias for the localization entry point.

    The current catalogs remain compatible with legacy Chinese msgids.
    """
    message_id = _SEMANTIC_MSGIDS.get(key, key)
    text = gt(message_id, model=model, lang=language, **kwargs)
    if message_id == key and '.' in key and text == key:
        _log.warning('Missing translation key: %s', key)
        return f'[{key}]'
    return text


def get_source_msgid(
    displayed_text: str,
    model: str = 'ui',
    language: str | None = None,
) -> str | None:
    """Find the source msgid for a currently displayed translated string."""
    if not displayed_text:
        return None
    current_language = normalize_language(language or _default_lang)
    if current_language == 'zh-CN':
        return displayed_text
    if model not in _gt:
        _gt[model] = {}
    if current_language not in _gt[model]:
        _gt[model][current_language] = get_translations(model, current_language)
    translations = _gt[model][current_language]
    if translations is None:
        return None
    catalog = getattr(translations, '_catalog', {})
    if displayed_text in catalog:
        return displayed_text
    for msgid, translated in catalog.items():
        if isinstance(msgid, str) and msgid and translated == displayed_text:
            return msgid
    return None


def coalesce_gt(msg: str | None, default: str, model: str = 'ui', lang: str | None = None) -> str:
    """
    带有默认值的获取多语言
    :param msg: 原字符串
    :param default: 默认值
    :param model:
    :param lang:
    :return:
    """
    if lang is None:
        lang = _default_lang
    return gt(msg if msg is not None else default, model, lang)


def update_default_lang(lang: str):
    global _default_lang
    normalized = normalize_language(lang)
    if normalized == _default_lang:
        return normalized
    _default_lang = normalized
    for callback in tuple(_language_changed_callbacks):
        try:
            callback(normalized)
        except Exception:
            _log.exception('语言切换回调执行失败')
    return normalized


def get_default_lang() -> str:
    """
    获取默认语言
    :return:
    """
    global _default_lang
    return _default_lang


def subscribe_language_changed(callback: Callable[[str], None]) -> None:
    """Subscribe to language changes so Qt views can refresh visible text."""
    if callback not in _language_changed_callbacks:
        _language_changed_callbacks.append(callback)


def unsubscribe_language_changed(callback: Callable[[str], None]) -> None:
    """Unsubscribe from language changes."""
    if callback in _language_changed_callbacks:
        _language_changed_callbacks.remove(callback)


class I18nManager:
    """Application-level localization manager."""

    @property
    def language(self) -> str:
        """Return the current language code."""
        return get_default_lang()

    def set_language(self, language: str) -> str:
        """Switch language and notify registered views."""
        return update_default_lang(language)

    def subscribe(self, callback: Callable[[str], None]) -> None:
        """Register a language-change callback."""
        subscribe_language_changed(callback)

    def unsubscribe(self, callback: Callable[[str], None]) -> None:
        """Remove a language-change callback."""
        unsubscribe_language_changed(callback)


i18n_manager = I18nManager()
