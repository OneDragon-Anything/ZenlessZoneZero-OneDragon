import gettext
import locale
import os
from typing import Optional

from one_dragon.utils import os_utils

_gt = {}
_default_lang = 'zh'


def detect_language():
    """自动检测系统语言"""
    try:
        system_locale = locale.getdefaultlocale()[0]
        if system_locale and system_locale.startswith('zh'):
            return 'zh'
        else:
            return 'en'
    except:
        return 'zh'


def detect_and_set_default_language():
    """
    检测系统语言并设置为默认语言
    :return:
    """
    return update_default_lang(detect_language())

def get_translations(model: str, lang: str):
    """
    加载语音
    :param model: 模块 将ocr 界面 日志等翻译区分开来
    :param lang: 语言
    :return:
    """
    translate_path = os_utils.get_path_under_work_dir('assets', 'text', 'output')
    lang_dir = os.path.join(translate_path, lang, 'LC_MESSAGES', f'{model}.mo')
    # 未有对应的文本mo文件
    if not os.path.exists(lang_dir):
        return None
    gettext.bindtextdomain(model, translate_path)
    translation = gettext.translation(model, localedir=translate_path, languages=[lang])
    # 注册翻译函数为全局函数
    translation.install()
    return translation


def gt(msg: str, model: str = 'ui', lang: str = None) -> str:
    if msg is None or len(msg) == 0:
        return ''
    if lang is None:
        lang = _default_lang
    if model not in _gt:
        _gt[model] = {}
    if lang not in _gt[model]:
        _gt[model][lang] = get_translations(model, lang)

    trans = _gt[model][lang]
    return trans.gettext(msg) if trans is not None else msg


def coalesce_gt(msg: Optional[str], default: str, model: str = 'ui', lang: str = None) -> str:
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
    _default_lang = lang


def get_default_lang() -> str:
    """
    获取默认语言
    :return:
    """
    global _default_lang
    return _default_lang
