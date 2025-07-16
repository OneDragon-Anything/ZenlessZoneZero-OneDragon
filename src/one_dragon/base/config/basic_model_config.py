from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.base.matcher.ocr.onnx_ocr_matcher import DEFAULT_OCR_MODEL_NAME, get_ocr_model_dir, \
    get_ocr_download_url_github, get_ocr_download_url_gitee, get_final_file_list
from one_dragon.base.web.common_downloader import CommonDownloaderParam


class BasicModelConfig(YamlConfig):

    def __init__(self):
        YamlConfig.__init__(self, 'model', instance_idx=None)

    @property
    def ocr(self) -> str:
        return self.get('ocr', DEFAULT_OCR_MODEL_NAME)

    @ocr.setter
    def ocr(self, new_value: str) -> None:
        self.update('ocr', new_value)

    @property
    def ocr_gpu(self) -> bool:
        return self.get('ocr_gpu', False)

    @ocr_gpu.setter
    def ocr_gpu(self, new_value: bool) -> None:
        self.update('ocr_gpu', new_value)

    def using_old_model(self) -> bool:
        """
        是否在使用旧模型
        :return:
        """
        pass

def get_ocr_opts() -> list[ConfigItem]:
    models_list = [DEFAULT_OCR_MODEL_NAME]
    config_list: list[ConfigItem] = []
    for model in models_list:
        model_dir = get_ocr_model_dir(model)
        zip_file_name: str = f'{model}.zip'
        param = CommonDownloaderParam(
            save_file_path=model_dir,
            save_file_name=zip_file_name,
            github_release_download_url=get_ocr_download_url_github(model),
            gitee_release_download_url=get_ocr_download_url_gitee(model),
            check_existed_list=get_final_file_list(model),
        )
        config_list.append(
            ConfigItem(
                label=model,
                value=param,
            )
        )

    return config_list
