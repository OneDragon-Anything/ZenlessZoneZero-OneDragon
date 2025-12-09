import os
import time
import urllib.request
import zipfile
from typing import Optional, List

import onnxruntime as ort

from one_dragon.yolo.log_utils import log

_GH_PROXY_URL = 'https://ghfast.top'


class OnnxModelLoader:

    def __init__(self,
                 model_name: str,
                 model_download_url: str,
                 model_parent_dir_path: str = os.path.abspath(__file__),  # 默认使用本文件的目录
                 gh_proxy: bool = True,
                 gh_proxy_url: str = _GH_PROXY_URL,
                 personal_proxy: Optional[str] = '',
                 gpu: bool = False,
                 backup_model_name: Optional[str] = None,
                 ):
        self.model_name: str = model_name
        self.backup_model_name: str = backup_model_name  # 备用模型 默认在本地一定有的模型 在新模型无法下载使用时使用
        self.model_download_url: str = model_download_url  # 模型下载地址
        self.model_parent_dir_path: str = model_parent_dir_path
        self.model_dir_path = os.path.join(self.model_parent_dir_path, self.model_name)
        self.gh_proxy: bool = gh_proxy
        self.gh_proxy_url: str = gh_proxy_url
        self.personal_proxy: Optional[str] = personal_proxy
        self.gpu: bool = gpu  # 是否使用GPU加速

        # 从模型中读取到的输入输出信息
        self.session: ort.InferenceSession = None
        self.input_names: List[str] = []
        self.onnx_input_width: int = 0
        self.onnx_input_height: int = 0
        self.output_names: List[str] = []

        if not self.check_and_download_model():  # 新模型不ok
            log.error(f'模型 {self.model_name} 未下载成功 请尝试更换代理下载')
            log.info(f'尝试使用备用模型 {self.backup_model_name}')
            self.model_name = self.backup_model_name
            self.model_dir_path = os.path.join(self.model_parent_dir_path, self.model_name)

        self.load_model()

    def check_and_download_model(self) -> bool:
        """
        检查模型是否已经下载好了 如果目录不存在 或者缺少文件 则进行下载
        :return: 返回模型的目录
        """
        if not self.check_model_exists():
            download = self.download_model()
            if not download:
                return False
        return True

    def check_model_exists(self) -> bool:
        """
        检查模型是否已经下载好了，这里只能统一判断onnx是否存在，其它附属文件需要子类自行判断。
        :return:
        """
        onnx_path = os.path.join(self.model_dir_path, 'model.onnx')

        return os.path.exists(self.model_dir_path) and os.path.exists(onnx_path)

    def download_model(self) -> bool:
        """
        下载模型
        :return: 是否成功下载模型
        """
        if not os.path.exists(self.model_dir_path):
            os.mkdir(self.model_dir_path)

        download_url = f'{self.model_download_url}/{self.model_name}.zip'
        if self.personal_proxy is not None and len(self.personal_proxy) > 0:
            os.environ['http_proxy'] = self.personal_proxy
            os.environ['https_proxy'] = self.personal_proxy
        elif self.gh_proxy:
            download_url = f'{self.gh_proxy_url}/{self.model_download_url}/{self.model_name}.zip'
        log.info('开始下载 %s %s', self.model_name, download_url)
        zip_file_path = os.path.join(self.model_dir_path, f'{self.model_name}.zip')
        last_log_time = time.time()

        def log_download_progress(block_num, block_size, total_size):
            nonlocal last_log_time
            if time.time() - last_log_time < 1:
                return
            last_log_time = time.time()
            downloaded = block_num * block_size / 1024.0 / 1024.0
            total_size_mb = total_size / 1024.0 / 1024.0
            progress = downloaded / total_size_mb * 100
            log.info(f"正在下载 {self.model_name}: {downloaded:.2f}/{total_size_mb:.2f} MB ({progress:.2f}%)")

        try:
            _, _ = urllib.request.urlretrieve(download_url, zip_file_path, log_download_progress)
            log.info('下载完成 %s', self.model_name)
            self.unzip_model(zip_file_path)
            return True
        except Exception:
            log.error('下载失败模型失败', exc_info=True)
            return False

    def unzip_model(self, zip_file_path: str):
        """
        解压文件
        :param zip_file_path: 压缩文件路径
        :return:
        """
        log.info('开始解压文件 %s', zip_file_path)

        if not os.path.exists(self.model_dir_path):
            os.mkdir(self.model_dir_path)

        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(self.model_dir_path)

        log.info('解压完成 %s', zip_file_path)

    def load_model(self) -> None:
        """
        加载模型
        :return:
        """
        availables = ort.get_available_providers()

        if self.gpu:
            if 'CUDAExecutionProvider' in availables:
                providers = ['CUDAExecutionProvider']
            elif 'DmlExecutionProvider' in availables:
                providers = ['DmlExecutionProvider']
            else:
                providers = ['CPUExecutionProvider']
                log.warning('未找到GPU执行提供程序，回退到CPU')
        else:
            providers = ['CPUExecutionProvider']

        onnx_path = os.path.join(self.model_dir_path, 'model.onnx')
        log.info('加载模型 %s', onnx_path)

        self.session = ort.InferenceSession(
            onnx_path,
            providers=providers,
        )
        self.get_input_details()
        self.get_output_details()

    def get_input_details(self):
        model_inputs = self.session.get_inputs()
        self.input_names = [model_inputs[i].name for i in range(len(model_inputs))]

        shape = model_inputs[0].shape
        self.onnx_input_height = shape[2]
        self.onnx_input_width = shape[3]

    def get_output_details(self):
        model_outputs = self.session.get_outputs()
        self.output_names = [model_outputs[i].name for i in range(len(model_outputs))]
