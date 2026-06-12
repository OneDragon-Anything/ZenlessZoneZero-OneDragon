import time
import numpy as np
from .imaug import transform, create_operators
from .db_postprocess import DBPostProcess
from .logger import get_logger
from .predict_base import PredictBase

log = get_logger("predict_det")


class TextDetector(PredictBase):
    def __init__(self, args):
        self.args = args
        self.det_algorithm = args.det_algorithm
        pre_process_list = [
            {
                "DetResizeForTest": {
                    "limit_side_len": args.det_limit_side_len,
                    "limit_type": args.det_limit_type,
                }
            },
            {
                "NormalizeImage": {
                    "std": [0.229, 0.224, 0.225],
                    "mean": [0.485, 0.456, 0.406],
                    "scale": "1./255.",
                    "order": "hwc",
                }
            },
            {"ToCHWImage": None},
            {"KeepKeys": {"keep_keys": ["image", "shape"]}},
        ]
        postprocess_params = {}
        postprocess_params["name"] = "DBPostProcess"
        postprocess_params["thresh"] = args.det_db_thresh
        postprocess_params["box_thresh"] = args.det_db_box_thresh
        postprocess_params["max_candidates"] = getattr(args, "det_db_max_candidates", 1000)
        postprocess_params["unclip_ratio"] = args.det_db_unclip_ratio
        postprocess_params["use_dilation"] = args.use_dilation
        postprocess_params["score_mode"] = args.det_db_score_mode
        postprocess_params["box_type"] = args.det_box_type

        # 实例化前处理操作类
        self.preprocess_op = create_operators(pre_process_list)
        # self.postprocess_op = build_post_process(postprocess_params)
        # 实例化后处理操作类
        self.postprocess_op = DBPostProcess(**postprocess_params)

        # 初始化模型
        self.det_onnx_session = self.get_onnx_session(args.det_model_dir, args.use_gpu, gpu_id = args.gpu_id)
        self.det_input_name = self.get_input_name(self.det_onnx_session)
        self.det_output_name = self.get_output_name(self.det_onnx_session)
        log.info("Detection model loaded: {}", args.det_model_dir)

        # 预热模型，避免因为算子懒加载导致前几次推理耗时增加 2-10 倍
        dummy = np.zeros((1, 3, int(args.det_limit_side_len), int(args.det_limit_side_len)), dtype=np.float32)
        self.det_onnx_session.run(self.det_output_name, {self.det_input_name[0]: dummy})

    def order_points_clockwise(self, pts):
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        tmp = np.delete(pts, (np.argmin(s), np.argmax(s)), axis=0)
        diff = np.diff(np.array(tmp), axis=1)
        rect[1] = tmp[np.argmin(diff)]
        rect[3] = tmp[np.argmax(diff)]
        return rect

    def clip_det_res(self, points, img_height, img_width):
        for pno in range(points.shape[0]):
            points[pno, 0] = int(min(max(points[pno, 0], 0), img_width - 1))
            points[pno, 1] = int(min(max(points[pno, 1], 0), img_height - 1))
        return points

    def filter_tag_det_res(self, dt_boxes, image_shape):
        img_height, img_width = image_shape[0:2]
        dt_boxes_new = []
        for box in dt_boxes:
            if type(box) is list:
                box = np.array(box)
            box = self.order_points_clockwise(box)
            box = self.clip_det_res(box, img_height, img_width)
            rect_width = int(np.linalg.norm(box[0] - box[1]))
            rect_height = int(np.linalg.norm(box[0] - box[3]))
            if rect_width <= 3 or rect_height <= 3:
                continue
            dt_boxes_new.append(box)
        dt_boxes = np.array(dt_boxes_new)
        return dt_boxes

    def filter_tag_det_res_only_clip(self, dt_boxes, image_shape):
        img_height, img_width = image_shape[0:2]
        dt_boxes_new = []
        for box in dt_boxes:
            if type(box) is list:
                box = np.array(box)
            box = self.clip_det_res(box, img_height, img_width)
            dt_boxes_new.append(box)
        dt_boxes = np.array(dt_boxes_new)
        return dt_boxes

    def __call__(self, img):
        ori_shape = img.shape
        data = {"image": img}

        data = transform(data, self.preprocess_op)
        img, shape_list = data
        if img is None:
            return None, 0
        img = np.expand_dims(img, axis=0)
        shape_list = np.expand_dims(shape_list, axis=0)

        input_feed = self.get_input_feed(self.det_input_name, img)
        t0 = time.time()
        outputs = self.run_onnx_session(self.det_onnx_session, self.det_output_name, input_feed=input_feed)
        log.debug("Detection inference time: {:.3f}s", time.time() - t0)

        preds = {}
        preds["maps"] = outputs[0]

        post_result = self.postprocess_op(preds, shape_list)
        dt_boxes = post_result[0]["points"]

        if self.args.det_box_type == "poly":
            dt_boxes = self.filter_tag_det_res_only_clip(dt_boxes, ori_shape)
        else:
            dt_boxes = self.filter_tag_det_res(dt_boxes, ori_shape)

        return dt_boxes
