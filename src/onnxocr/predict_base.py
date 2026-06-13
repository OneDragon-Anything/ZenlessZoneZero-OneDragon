from onnxocr.inference_engine import InferenceSession, create_session
from onnxocr.logger import get_logger

log = get_logger("predict_base")
from one_dragon.utils import gpu_executor
from one_dragon.utils.log_utils import log


class PredictBase:
    def __init__(self) -> None:
        pass

    def get_onnx_session(self, model_dir: str, use_gpu: bool, gpu_id: int = 0) -> InferenceSession:
        return create_session(model_dir, use_gpu=use_gpu, gpu_id=gpu_id)

    def get_output_name(self, onnx_session):
        """
        output_name = onnx_session.get_outputs()[0].name
        :param onnx_session:
        :return:
        """
        output_name = []
        for node in onnx_session.get_outputs():
            output_name.append(node.name)
        return output_name

    def get_input_name(self, onnx_session):
        """
        input_name = onnx_session.get_inputs()[0].name
        :param onnx_session:
        :return:
        """
        input_name = []
        for node in onnx_session.get_inputs():
            input_name.append(node.name)
        return input_name

    def get_input_feed(self, input_name, image_numpy):
        """
        input_feed={self.input_name: image_numpy}
        :param input_name:
        :param image_numpy:
        :return:
        """
        input_feed = {}
        for name in input_name:
            input_feed[name] = image_numpy
        return input_feed

    def run_onnx_session(self, onnx_session, output_names, input_feed):
        return gpu_executor.run_session(onnx_session, output_names, input_feed=input_feed)
