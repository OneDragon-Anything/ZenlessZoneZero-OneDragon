import argparse
import time
from pathlib import Path

from .logger import get_logger
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
    if model_size:
        size = str(model_size).lower()
    elif model_name:
        normalized = str(model_name).lower()
        size = next((name for name in PPOCRV6_MODEL_CONFIGS if name in normalized), None)
    else:
        size = None

    if size not in PPOCRV6_MODEL_CONFIGS:
        return None
    return size


def _build_ppocrv6_defaults(kwargs):
    """为 PP-OCRv6 模型构建默认参数。如果不是 v6 模型则返回空字典，保证 v5 兼容。"""
    model_name = kwargs.pop("ocr_model_name", None)
    model_size = kwargs.pop("ocr_model_size", None)
    size = _normalize_ppocrv6_size(model_name=model_name, model_size=model_size)
    if not size:
        return {}

    model_root = Path(__file__).resolve().parent / "models" / "ppocrv6"
    config = PPOCRV6_MODEL_CONFIGS[size]

    defaults = {
        "det_model_dir": str(model_root / size / "det" / "det.onnx"),
        "rec_model_dir": str(model_root / size / "rec" / "rec.onnx"),
        "rec_char_dict_path": str(model_root / config["rec_char_dict_path"]),
        "rec_image_shape": "3, 48, 320",
        "det_limit_side_len": 736,
        "det_limit_type": "min",
        "det_db_thresh": 0.2,
        "det_db_box_thresh": config["det_db_box_thresh"],
        "det_db_unclip_ratio": 1.4,
        "det_db_max_candidates": 3000,
    }
    return {key: value for key, value in defaults.items() if key not in kwargs}


class ONNXPaddleOcr(TextSystem):
    """
    onnxruntime支持的opset
    https://onnxruntime.ai/docs/reference/compatibility.html
    """

    def __init__(self, **kwargs):
        # 默认参数
        parser = init_args()
        inference_args_dict = {}
        for action in parser._actions:
            inference_args_dict[action.dest] = action.default
        params = argparse.Namespace(**inference_args_dict)

        model_defaults = _build_ppocrv6_defaults(kwargs)
        params.rec_image_shape = "3, 48, 320"

        # 根据传入的参数覆盖更新默认参数
        params.__dict__.update(model_defaults)
        params.__dict__.update(**kwargs)

        # 初始化模型
        super().__init__(params)
        log.info("OCR model initialized: det=True, cls={}, rec=True", self.use_angle_cls)

    def ocr(self, img, det=True, rec=True, cls=True) -> list:
        if cls is True and self.use_angle_cls is False:
            log.warning(
                "Since the angle classifier is not initialized, the angle classifier will not be used during the forward process"
            )

        try:
            if det and rec:
                ocr_res = []
                dt_boxes, rec_res = self.__call__(img, cls)
                tmp_res = [[box.tolist(), res] for box, res in zip(dt_boxes, rec_res)]
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
        except Exception as e:
            print(e)
            from one_dragon.utils import debug_utils
            debug_utils.save_debug_image(image=img[0], prefix='ocr_error')
            return []


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
    from one_dragon.utils import os_utils, debug_utils

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
    print("total time: {:.3f}".format(e - s))
    print("result:", result)
    for box in result[0]:
        print(box)


if __name__ == "__main__":
    __debug()
