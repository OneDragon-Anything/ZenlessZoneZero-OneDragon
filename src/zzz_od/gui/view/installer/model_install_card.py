import os
from collections.abc import Callable

from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor

from one_dragon.base.matcher.ocr.onnx_ocr_matcher import (
    get_final_file_list,
    get_ocr_download_url_gitee,
    get_ocr_download_url_github,
    get_ocr_model_dir,
)
from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.base.web.zip_downloader import ZipDownloader
from one_dragon.utils import yolo_config_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon.yolo.yolo_utils import (
    get_gitee_model_download_url,
    get_github_model_download_url,
)
from one_dragon_qt.widgets.install_card.base_install_card import BaseInstallCard
from zzz_od.config.model_config import YOLO_RELEASE_TAG

# 需要下载的 OCR 模型（默认模型）
_OCR_MODELS = ['ppocrv5']
# 需要下载的 YOLO 模型：(分类目录, 模型名)
_YOLO_MODELS = [
    ('flash_classifier', 'yolov8n-640-flash-20250921'),
    ('hollow_zero_event', 'yolov8s-736-hollow-zero-event-0126'),
    ('lost_void_det', 'yolov26n-736-lost-void-det-20260630'),
]


class ModelInstallCard(BaseInstallCard):
    """模型下载卡：检查并下载 OCR 与 YOLO 模型。"""

    def __init__(self, ctx: OneDragonEnvContext, parent=None):
        BaseInstallCard.__init__(
            self,
            ctx=ctx,
            title_cn='模型下载',
            install_method=self.install_models,
            install_btn_icon=FluentIcon.DOWNLOAD,
            parent=parent,
        )

    # -------------------- 状态检查 -------------------- #

    def get_missing_models(self) -> list[str]:
        """返回缺失的模型名称列表（用于状态展示）。"""
        missing: list[str] = []
        for ocr_model_name in _OCR_MODELS:
            if not self._check_ocr_model(ocr_model_name):
                missing.append(ocr_model_name)
        for category, model_name in _YOLO_MODELS:
            if not yolo_config_utils.is_model_existed(category, model_name):
                missing.append(model_name)
        return missing

    @staticmethod
    def _check_ocr_model(ocr_model_name: str) -> bool:
        """检查 OCR 模型文件是否齐全。"""
        return all(os.path.exists(path) for path in get_final_file_list(ocr_model_name))

    def get_display_content(self) -> tuple[QIcon, str]:
        """
        获取需要显示的状态
        :return: 显示的图标、文本
        """
        missing = self.get_missing_models()
        if not missing:
            self._installed = True
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
            msg = gt('模型已齐全')
        else:
            self._installed = False
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value)
            msg = f"{gt('缺少模型')}: {', '.join(missing)}"

        return icon, msg

    # -------------------- 安装 -------------------- #

    def install_models(
        self,
        progress_callback: Callable[[float, str], None],
    ) -> tuple[bool, str]:
        """依次下载缺失的 OCR 与 YOLO 模型。"""
        missing = self.get_missing_models()
        if not missing:
            return True, gt('模型已齐全')

        total = len(missing)
        for done, model_name in enumerate(missing, start=1):
            if progress_callback is not None:
                progress_callback(
                    (done - 1) / total,
                    f"{gt('正在下载模型')}: {model_name}",
                )
            log.info('开始下载模型 %s', model_name)
            success = self._download_model(model_name, progress_callback)
            if not success:
                return False, f"{gt('模型下载失败')}: {model_name}"
            if progress_callback is not None:
                progress_callback(done / total, f"{gt('模型下载完成')}: {model_name}")

        return True, gt('模型下载完成')

    def _download_model(
        self,
        model_name: str,
        progress_callback: Callable[[float, str], None],
    ) -> bool:
        """下载单个模型，返回是否成功。"""
        if model_name in _OCR_MODELS:
            return self._download_ocr_model(model_name, progress_callback)
        for category, yolo_name in _YOLO_MODELS:
            if model_name == yolo_name:
                return self._download_yolo_model(category, model_name, progress_callback)
        log.warning('未知模型 %s，跳过下载', model_name)
        return False

    def _download_ocr_model(
        self,
        ocr_model_name: str,
        progress_callback: Callable[[float, str], None],
    ) -> bool:
        """下载 OCR 模型并解压到模型目录。"""
        models_dir = get_ocr_model_dir(ocr_model_name)
        os.makedirs(models_dir, exist_ok=True)
        param = CommonDownloaderParam(
            save_file_path=models_dir,
            save_file_name=f'{ocr_model_name}.zip',
            github_release_download_url=get_ocr_download_url_github(ocr_model_name),
            gitee_release_download_url=get_ocr_download_url_gitee(ocr_model_name),
            check_existed_list=get_final_file_list(ocr_model_name),
        )
        downloader = ZipDownloader(param)
        return downloader.download(
            download_by_github=True,
            download_by_gitee=True,
            proxy_url=self._get_proxy_url(),
            ghproxy_url=self._get_ghproxy_url(),
            progress_callback=progress_callback,
        )

    def _download_yolo_model(
        self,
        category: str,
        model_name: str,
        progress_callback: Callable[[float, str], None],
    ) -> bool:
        """下载 YOLO 模型并解压到分类目录。"""
        model_dir = yolo_config_utils.get_model_dir(category, model_name)
        os.makedirs(model_dir, exist_ok=True)
        param = CommonDownloaderParam(
            save_file_path=model_dir,
            save_file_name=f'{model_name}.zip',
            github_release_download_url=f'{get_github_model_download_url(YOLO_RELEASE_TAG)}/{model_name}.zip',
            gitee_release_download_url=f'{get_gitee_model_download_url(YOLO_RELEASE_TAG)}/{model_name}.zip',
            check_existed_list=[
                os.path.join(model_dir, 'model.onnx'),
                os.path.join(model_dir, 'labels.csv'),
            ],
        )
        downloader = ZipDownloader(param)
        return downloader.download(
            download_by_github=True,
            download_by_gitee=True,
            proxy_url=self._get_proxy_url(),
            ghproxy_url=self._get_ghproxy_url(),
            progress_callback=progress_callback,
        )

    def _get_proxy_url(self) -> str | None:
        """获取个人代理地址。"""
        if self.ctx.env_config.is_personal_proxy:
            return self.ctx.env_config.personal_proxy
        return None

    def _get_ghproxy_url(self) -> str | None:
        """获取 GitHub 加速代理地址。"""
        if self.ctx.env_config.is_gh_proxy:
            return self.ctx.env_config.gh_proxy_url
        return None
