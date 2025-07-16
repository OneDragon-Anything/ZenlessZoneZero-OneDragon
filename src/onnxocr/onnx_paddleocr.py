import time

from onnxocr.predict_system import TextSystem
from onnxocr.utils import infer_args as init_args
from onnxocr.utils import str2bool, draw_ocr
import argparse
import sys


class ONNXPaddleOcr(TextSystem):
    def __init__(self, **kwargs):
        # 默认参数
        parser = init_args()
        inference_args_dict = {}
        for action in parser._actions:
            inference_args_dict[action.dest] = action.default
        params = argparse.Namespace(**inference_args_dict)

        # params.rec_image_shape = "3, 32, 320"
        params.rec_image_shape = "3, 48, 320"

        # 根据传入的参数覆盖更新默认参数
        params.__dict__.update(**kwargs)

        # 初始化模型
        super().__init__(params)

    def ocr(self, img, det=True, rec=True, cls=True):
        if cls == True and self.use_angle_cls == False:
            print(
                "Since the angle classifier is not initialized, the angle classifier will not be uesd during the forward process"
            )

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
    import cv2
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
