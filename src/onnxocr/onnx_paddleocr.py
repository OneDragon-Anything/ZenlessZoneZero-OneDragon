import argparse
import time
from pathlib import Path
from typing import Any

from cv2.typing import MatLike

from onnxocr.logger import get_logger
from onnxocr.predict_system import TextSystem
from onnxocr.utils import draw_ocr
from onnxocr.utils import infer_args as init_args

log = get_logger("onnx_paddleocr")

PPOCRV6_MODEL_CONFIGS = {
    "medium": {
        "det_db_box_thresh": 0.45,
        "rec_char_dict_path": "ppocrv6_dict.txt",
    },
    "small": {
        "det_db_box_thresh": 0.45,
        "rec_char_dict_path": "ppocrv6_dict.txt",
    },
    "tiny": {
        "det_db_box_thresh": 0.4,
        "rec_char_dict_path": "ppocrv6_tiny_dict.txt",
    },
}


def _normalize_ppocrv6_size(model_name=None, model_size=None):
    if not model_name:
        return None
    if model_size:
        size = str(model_size).lower()
    else:
        normalized = str(model_name).lower()
        size = next((name for name in PPOCRV6_MODEL_CONFIGS if name in normalized), None)

    if size not in PPOCRV6_MODEL_CONFIGS:
        return None
    return size


def _build_ppocrv6_defaults(kwargs):
    """为 PP-OCRv6 模型构建默认参数。如果不是 v6 模型则返回空字典，保证 v5 兼容。"""
    model_name = kwargs.pop("ocr_model_name", None)
    if not model_name:
        kwargs.pop("ocr_model_size", None)
        return {}
    model_size = kwargs.pop("ocr_model_size", None)
    size = _normalize_ppocrv6_size(model_name=model_name, model_size=model_size)
    if not size:
        return {}

    from one_dragon.utils import os_utils
    model_root = Path(os_utils.get_path_under_work_dir('assets', 'models', 'onnx_ocr', model_name))
    config = PPOCRV6_MODEL_CONFIGS[size]

    defaults = {
        "det_model_dir": str(model_root / "det.onnx"),
        "rec_model_dir": str(model_root / "rec.onnx"),
        "rec_char_dict_path": str(model_root / config["rec_char_dict_path"]),
        "rec_image_shape": "3, 48, 320",
        "det_limit_side_len": 960,
        "det_limit_type": "max",
        "det_db_thresh": 0.3,
        "det_db_box_thresh": config["det_db_box_thresh"],
        "det_db_unclip_ratio": 1.5,
        "det_db_max_candidates": 1000,
    }
    return {key: value for key, value in defaults.items() if key not in kwargs}


class ONNXPaddleOcr(TextSystem):
    """
    onnxruntime支持的opset
    https://onnxruntime.ai/docs/reference/compatibility.html
    """

    def __init__(
        self,
        use_gpu: bool = False,
        det_model_dir: str | None = None,
        rec_model_dir: str | None = None,
        cls_model_dir: str | None = None,
        rec_char_dict_path: str | None = None,
        vis_font_path: str | None = None,
        use_angle_cls: bool = False,
        det_limit_side_len: float = 960.0,
        ocr_model_size: str | None = None,
        ocr_model_name: str | None = None,
    ) -> None:
        # 默认参数
        parser = init_args()
        inference_args_dict = {}
        for action in parser._actions:
            inference_args_dict[action.dest] = action.default
        params = argparse.Namespace(**inference_args_dict)

        kwargs = {
            "use_gpu": use_gpu,
            "det_model_dir": det_model_dir,
            "rec_model_dir": rec_model_dir,
            "cls_model_dir": cls_model_dir,
            "rec_char_dict_path": rec_char_dict_path,
            "vis_font_path": vis_font_path,
            "use_angle_cls": use_angle_cls,
            "det_limit_side_len": det_limit_side_len,
            "ocr_model_size": ocr_model_size,
            "ocr_model_name": ocr_model_name,
        }
        # 过滤掉 None 值，避免覆盖默认行为
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        model_defaults = _build_ppocrv6_defaults(filtered_kwargs)
        params.rec_image_shape = "3, 48, 320"

        # 根据传入的参数覆盖更新默认参数
        params.__dict__.update(model_defaults)
        params.__dict__.update(**filtered_kwargs)

        # 初始化模型
        super().__init__(params)
        log.info("OCR model initialized: det=True, cls={}, rec=True", self.use_angle_cls)

    def ocr(
        self,
        img: MatLike | list[MatLike],
        det: bool = True,
        rec: bool = True,
        cls: bool = True
    ) -> list[Any]:
        """对输入图像进行文字检测、方向分类及文本识别。

        Args:
            img: 待识别的图像，可以是单张图像 (MatLike) 或图像列表 (List[MatLike])。
            det: 是否进行文字检测。若为 True，会先检测出所有文字区域的包围框。
            rec: 是否进行文字识别。若为 True，会对文字区域进行文本内容识别。
            cls: 是否进行方向角度分类校正。若为 True 且初始化时启用了角度分类模型，会校正文字方向。

        Returns:
            根据参数组合，返回不同层级的嵌套列表：
            1. det=True, rec=True (默认):
               返回 [[[box, (text_result, score)], ...]]
               其中 box 是四点坐标列表 [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]，text_result 是识别的文本，score 是置信度。
            2. det=True, rec=False:
               返回 [[box, box, ...]]，仅包含检测到的所有包围框坐标。
            3. det=False, rec=True (或 det=False, rec=False):
               返回识别结果列表或分类结果列表。
        """
        if cls is True and self.use_angle_cls is False:
            log.warning(
                "Since the angle classifier is not initialized, the angle classifier will not be used during the forward process"
            )

        try:
            if det and rec:
                ocr_res = []
                dt_boxes, rec_res = self.__call__(img, cls)
                tmp_res = [[box.tolist(), res] for box, res in zip(dt_boxes, rec_res, strict=True)]
                ocr_res.append(tmp_res)
                return ocr_res
            elif det and not rec:
                ocr_res = []
                dt_boxes = self.text_detector(img)
                tmp_res = [box.tolist() for box in dt_boxes]
                ocr_res.append(tmp_res)
                return ocr_res
            else:
                ocr_res = []
                cls_res = []

                if not isinstance(img, list):
                    img = [img]
                if self.use_angle_cls and cls:
                    img, cls_res_tmp = self.text_classifier(img)
                    if not rec:
                        cls_res.append(cls_res_tmp)
                rec_res = self.text_recognizer(img)
                ocr_res.append(rec_res)

                if not rec:
                    return cls_res
                return ocr_res
        except Exception:
            from one_dragon.utils.log_utils import log as od_log
            od_log.error('OCR推理出错', exc_info=True)
            try:
                from one_dragon.utils import debug_utils
                debug_image = img[0] if isinstance(img, list) else img
                debug_utils.save_debug_image(image=debug_image, prefix='ocr_error')
            except Exception:
                od_log.warning('保存OCR错误调试图片失败', exc_info=True)
            raise


def sav2Img(org_img, result, name="draw_ocr.jpg"):
    # 显示结果
    from PIL import Image

    result = result[0]
    # image = Image.open(img_path).convert('RGB')
    # 图像转BGR2RGB
    image = org_img[:, :, ::-1]
    boxes = [line[0] for line in result]
    txts = [line[1][0] for line in result]
    scores = [line[1][1] for line in result]
    im_show = draw_ocr(image, boxes, txts, scores)
    im_show = Image.fromarray(im_show)
    im_show.save(name)


def __debug():
    import os

    from one_dragon.utils import debug_utils, os_utils

    models_dir = os_utils.get_path_under_work_dir('assets', 'models', 'onnx_ocr', 'ppocrv5')

    model = ONNXPaddleOcr(
                    use_angle_cls=False, use_gpu=False,
                    det_model_dir=os.path.join(models_dir, 'det.onnx'),
                    rec_model_dir=os.path.join(models_dir, 'rec.onnx'),
                    cls_model_dir=os.path.join(models_dir, 'cls.onnx'),
                    rec_char_dict_path=os.path.join(models_dir, 'ppocrv5_dict.txt'),
                    vis_font_path=os.path.join(models_dir, 'simfang.ttf'),
                )

    img = debug_utils.get_debug_image('1')
    s = time.time()
    result = model.ocr(img)
    e = time.time()
    print(f"total time: {e - s:.3f}")
    print("result:", result)
    for box in result[0]:
        print(box)


if __name__ == "__main__":
    __debug()
