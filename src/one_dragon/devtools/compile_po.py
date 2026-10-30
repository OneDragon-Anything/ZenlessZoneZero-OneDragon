import os

import polib

from one_dragon.utils import os_utils


def compile_lang(model: str, lang: str):
    """
    将特定语言的文件编译成mo文件
    :param model: 模块 不同模块的多语言文本区分
    :param lang: 语言 cn
    :return: None
    """
    base_dir = os_utils.get_path_under_work_dir('assets', 'text')
    po_file_path = os.path.join(base_dir, model, '%s.po' % lang)

    output_dir = os_utils.get_path_under_work_dir('assets', 'text', 'output', lang, 'LC_MESSAGES')
    mo_file_path = os.path.join(output_dir, '%s.mo' % model)

    po = polib.pofile(po_file_path)
    po.save_as_mofile(mo_file_path)


def compile_po_files():
    """
    将不同语言的po文件编译成mo
    :return:
    """
    for model in ['game', 'ui']:
        for lang in ['zh', 'en']:
            compile_lang(model, lang)


if __name__ == '__main__':
    compile_po_files()
