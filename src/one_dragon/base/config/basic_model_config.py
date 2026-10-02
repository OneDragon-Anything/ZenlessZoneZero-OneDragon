from dataclasses import dataclass
from pathlib import Path

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.base.matcher.ocr.onnx_ocr_matcher import (
    DEFAULT_OCR_MODEL_NAME,
    PPOCRV6_MODEL_NAME,
    get_final_file_list,
    get_ocr_download_urls,
    get_ocr_model_dir,
)
from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.envs.repo_config import ModelResourceDefinition, RepoConfig
from one_dragon.utils import yolo_config_utils


@dataclass(frozen=True, slots=True)
class ModelUpdateInfo:
    """框架检查后得到的一项模型更新。"""

    definition: ModelResourceDefinition
    current_model: str
    target_model: str
    current_files_missing: bool
    download_param: CommonDownloaderParam


class BasicModelConfig(YamlConfig):

    def __init__(self, repo_config: RepoConfig) -> None:
        self.repo_config: RepoConfig = repo_config
        YamlConfig.__init__(self, 'model', instance_idx=None)

    @property
    def ocr(self) -> str:
        return self.get('ocr', DEFAULT_OCR_MODEL_NAME)

    @ocr.setter
    def ocr(self, new_value: str) -> None:
        self.update('ocr', new_value)

    @property
    def ocr_use_gpu(self) -> bool:
        return self.get('ocr_use_gpu', False)

    @ocr_use_gpu.setter
    def ocr_use_gpu(self, new_value: bool) -> None:
        self.update('ocr_use_gpu', new_value)

    def using_old_model(self) -> bool:
        """是否有项目模型未使用推荐版本。"""
        return any(
            self.get_model_current(resource) != resource.default_model
            for resource in self.get_model_resources()
        )

    def get_model_resources(self) -> tuple[ModelResourceDefinition, ...]:
        """返回项目声明的全部识别模型。"""
        return self.repo_config.model_resources

    def get_model_download_base_url(
        self,
        config_key: str,
        source_id: str = 'github',
    ) -> str:
        """获取模型加载器使用的 release 下载根地址。"""
        download_url = self.repo_config.get_model_download_base_url(
            config_key,
            source_id,
        )
        if not download_url:
            raise ValueError(
                f'模型资源 {config_key} 未配置下载源 {source_id}'
            )
        return download_url

    def get_model_current(self, resource: ModelResourceDefinition) -> str:
        """按声明读取模型当前版本。"""
        return str(self.get(resource.config_key, resource.default_model))

    def get_model_options(
        self,
        resource: ModelResourceDefinition,
    ) -> list[ConfigItem]:
        """构造资源管理页使用的可下载模型选项。"""
        models = yolo_config_utils.get_available_models(resource.config_key)
        if resource.default_model not in models:
            models.append(resource.default_model)
        return [
            ConfigItem(
                label=model,
                value=self._build_model_download_param(resource, model),
            )
            for model in models
        ]

    def get_model_update_params(self) -> list[ModelUpdateInfo]:
        """返回文件缺失或需要切换到推荐版本的模型。"""
        updates: list[ModelUpdateInfo] = []
        for resource in self.get_model_resources():
            current_model = self.get_model_current(resource)
            current_files_missing = not self._are_model_files_complete(
                resource,
                current_model,
            )
            if (
                current_model == resource.default_model
                and not current_files_missing
            ):
                continue
            updates.append(
                ModelUpdateInfo(
                    definition=resource,
                    current_model=current_model,
                    target_model=resource.default_model,
                    current_files_missing=current_files_missing,
                    download_param=self._build_model_download_param(
                        resource,
                        resource.default_model,
                    ),
                )
            )
        return updates

    def needs_model_download(self) -> bool:
        """是否存在项目模型文件缺失或推荐版本更新。"""
        return bool(self.get_model_update_params())

    @staticmethod
    def _are_model_files_complete(
        resource: ModelResourceDefinition,
        model: str,
    ) -> bool:
        """检查模型声明中的必需文件是否完整。"""
        model_dir = Path(
            yolo_config_utils.get_model_dir(resource.config_key, model)
        )
        return all(
            (model_dir / file_name).is_file()
            for file_name in resource.required_files
        )

    def _build_model_download_param(
        self,
        resource: ModelResourceDefinition,
        model: str,
    ) -> CommonDownloaderParam:
        """按模型声明构造通用下载参数。"""
        model_dir = Path(
            yolo_config_utils.get_model_dir(resource.config_key, model)
        )
        zip_file_name = f'{model}.zip'
        return CommonDownloaderParam(
            save_file_path=str(model_dir),
            save_file_name=zip_file_name,
            download_urls=self.repo_config.get_resource_asset_urls(
                resource.repo_key,
                resource.release_tag,
                zip_file_name,
            ),
            check_existed_list=[
                str(model_dir / file_name)
                for file_name in resource.required_files
            ],
        )


def get_ocr_opts() -> list[ConfigItem]:
    models_list = [DEFAULT_OCR_MODEL_NAME, PPOCRV6_MODEL_NAME]
    config_list: list[ConfigItem] = []
    for model in models_list:
        model_dir = get_ocr_model_dir(model)
        zip_file_name: str = f'{model}.zip'
        param = CommonDownloaderParam(
            save_file_path=model_dir,
            save_file_name=zip_file_name,
            download_urls=get_ocr_download_urls(model),
            check_existed_list=get_final_file_list(model),
        )
        config_list.append(
            ConfigItem(
                label=model,
                value=param,
            )
        )

    return config_list
