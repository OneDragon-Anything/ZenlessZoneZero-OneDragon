import gettext
import locale
import os
import yaml

from one_dragon.utils import os_utils


def detect_language():
    """自动检测系统语言"""
    try:
        system_locale = locale.getdefaultlocale()[0]
        if system_locale and system_locale.startswith('zh'):
            return 'zh'
        else:
            return 'en'
    except Exception:
        return 'zh'


def _init_default_lang() -> str:
    """从 custom.yml 读取默认界面语言 未配置或读取失败时按系统语言决定"""
    try:
        custom_path = os.path.join(os_utils.get_work_dir(), 'config', 'custom.yml')
        if not os.path.exists(custom_path):
            custom_path = os_utils.get_resource_path('config', 'custom.yml')
        if os.path.exists(custom_path):
            with open(custom_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    ui_lang = data.get('ui_language')
                    if ui_lang == 'auto':
                        return detect_language()
                    elif ui_lang:
                        return ui_lang
    except Exception:
        pass
    return detect_language()


def _init_default_game_lang() -> str:
    """从 game_account.yml 读取默认游戏语言 未配置或读取失败时使用中文"""
    try:
        work_dir = os_utils.get_work_dir()
        account_path = os.path.join(work_dir, 'config', '01', 'game_account.yml')
        if not os.path.exists(account_path):
            account_path = os.path.join(work_dir, 'config', 'game_account.yml')
        if os.path.exists(account_path):
            with open(account_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    game_lang = data.get('game_language')
                    if game_lang:
                        return 'zh' if game_lang in ('cn', 'zh') else game_lang
    except Exception:
        pass
    return 'zh'


_gt = {}
_default_lang = _init_default_lang()
_default_game_lang = _init_default_game_lang()


def detect_and_set_default_language():
    """
    检测系统语言并设置为默认语言
    :return:
    """
    return update_default_lang(detect_language())


def get_translations(model: str, lang: str):
    """
    加载语言
    :param model: 模块 将ocr 界面 日志等翻译区分开来
    :param lang: 语言
    :return:
    """
    translate_path = os_utils.get_resource_path('assets', 'text', 'output')
    lang_dir = os.path.join(translate_path, lang, 'LC_MESSAGES', f'{model}.mo')
    # 未有对应的文本mo文件
    if not os.path.exists(lang_dir):
        return None
    gettext.bindtextdomain(model, translate_path)
    translation = gettext.translation(model, localedir=translate_path, languages=[lang])
    # 注册翻译函数为全局函数
    translation.install()
    return translation


def gt(msg: str | None, model: str = 'ui', lang: str | None = None) -> str:
    """翻译文本 model 为 game / ocr 时使用游戏语言 其余使用界面语言 lang 可指定语言"""
    if msg is None or len(msg) == 0:
        return ''
    if lang is None:
        lang = _default_game_lang if model in ('game', 'ocr') else _default_lang
    if model not in _gt:
        _gt[model] = {}
    if lang not in _gt[model]:
        _gt[model][lang] = get_translations(model, lang)

    trans = _gt[model][lang]
    return trans.gettext(msg) if trans is not None else msg


def gt_compound(msg: str | None, sep: str = '-', model: str = 'ui') -> str:
    """
    翻译由分隔符组成的复合名称 例如配置模板名 "专属配队-艾莲"
    整体有翻译时优先使用整体翻译 否则逐段翻译后再拼接 新增模板无需逐个补充词条
    :param msg: 原文
    :param sep: 分隔符
    :param model: 翻译模块
    :return: 翻译后的名称
    """
    whole = gt(msg, model)
    if whole != msg or msg is None or sep not in msg:
        return whole
    parts = msg.split(sep)
    translated = [gt(part, model) for part in parts]
    if translated == parts:  # 中文等无翻译时保持原样
        return msg
    # 译文本身可能含 '-' (如 Quick-Swap) 用带空格的分隔符保证可读
    return f' {sep} '.join(translated)


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
        lang = _default_game_lang if model in ('game', 'ocr') else _default_lang
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


def update_game_lang(lang: str):
    """
    更新游戏客户端语言
    :param lang: 游戏语言 (cn/zh 规范化为 zh)
    """
    global _default_game_lang
    _default_game_lang = 'zh' if lang in ('cn', 'zh') else lang


def get_game_lang() -> str:
    """
    获取游戏客户端语言
    :return:
    """
    global _default_game_lang
    return _default_game_lang

