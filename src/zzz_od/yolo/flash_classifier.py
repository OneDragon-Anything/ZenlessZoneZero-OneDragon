from one_dragon.utils import yolo_config_utils
from one_dragon.yolo.yolov8_onnx_cls import Yolov8Classifier

# 模型类别名 → 闪避状态事件 的兼容映射
# 模型实际类别顺序以模型目录 labels.csv 为准；新迭代出现的变种
# 先按近似色降级复用现有状态，行为由闪避 yml 配置决定
LABEL_ALIAS_STATE = {
    'red': '闪避识别-红光',
    'purple': '闪避识别-红光',
    'yellow': '闪避识别-黄光',
    'orange': '闪避识别-黄光',
}


def load_label_states(model_dir_path: str) -> dict[int, str]:
    """
    读取模型目录 labels.csv 得到 idx → 闪避状态事件 的映射
    :param model_dir_path: 模型目录
    :return: idx → 状态事件名 不在别名表里的类别不会出现在结果中
    """
    import csv
    import os

    csv_path = os.path.join(model_dir_path, 'labels.csv')
    if not os.path.exists(csv_path):
        return {}
    result: dict[int, str] = {}
    with open(csv_path, encoding='utf-8') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if row[0] == 'idx':
                continue
            state = LABEL_ALIAS_STATE.get(row[1])
            if state is not None:
                result[int(row[0])] = state
    return result


class FlashClassifier(Yolov8Classifier):

    def __init__(
            self,
            model_download_url: str,
            model_name: str = 'yolov8n-640-flash-20250906',
            backup_model_name: str = 'yolov8n-640-flash-20250622',
            model_parent_dir_path: str = yolo_config_utils.get_model_category_dir('flash_classifier'),
            gh_proxy: bool = True,
            gh_proxy_url: str | None = None,
            personal_proxy: str | None = None,
            gpu: bool = False,
            keep_result_seconds: float = 2
    ):
        """
        :param model_name: 模型名称 在根目录下会有一个以模型名称创建的子文件夹
        :param model_parent_dir_path: 放置所有模型的根目录
        :param gpu: 是否启用GPU加速
        :param keep_result_seconds: 保留多长时间的识别结果
        """
        Yolov8Classifier.__init__(
            self,
            model_name=model_name,
            backup_model_name=backup_model_name,
            model_parent_dir_path=model_parent_dir_path,
            model_download_url=model_download_url,
            gh_proxy=gh_proxy,
            gh_proxy_url=gh_proxy_url,
            personal_proxy=personal_proxy,
            gpu=gpu,
            keep_result_seconds=keep_result_seconds
        )
        self.idx_2_state: dict[int, str] = load_label_states(self.model_dir_path)


def __debug():
    from one_dragon.utils import os_utils
    from zzz_od.context.zzz_context import ZContext

    ctx = ZContext()
    flash_classifier = FlashClassifier(
        model_download_url=ctx.model_config.get_model_download_base_url(
            'flash_classifier',
        ),
        model_parent_dir_path=os_utils.get_path_under_work_dir('assets', 'models', 'flash_classifier')
    )
    from one_dragon.utils import debug_utils
    result = flash_classifier.run(debug_utils.get_debug_image('_1750517690304'))
    print(result.class_idx)


if __name__ == '__main__':
    __debug()
