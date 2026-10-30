from one_dragon.base.config.basic_model_config import BasicModelConfig

_DEFAULT_FLASH_CLASSIFIER = 'yolov8n-640-flash-20250921'
_BACKUP_FLASH_CLASSIFIER = 'yolov8n-640-flash-20250906'

_DEFAULT_HOLLOW_ZERO_EVENT = 'yolov8s-736-hollow-zero-event-0126'
_BACKUP_HOLLOW_ZERO_EVENT = 'yolov8s-736-hollow-zero-event-1130'

_DEFAULT_LOST_VOID_DET = 'yolov26n-736-lost-void-det-20260630'
_BACKUP_LOST_VOID_DET = 'yolov8n-736-lost-void-det-20250921'

class ModelConfig(BasicModelConfig):

    @property
    def flash_classifier(self) -> str:
        """
        识别闪光模式 只允许使用最新的两个模型
        :return:
        """
        current = self.get('flash_classifier', _DEFAULT_FLASH_CLASSIFIER)
        if current != _DEFAULT_FLASH_CLASSIFIER and current != _BACKUP_FLASH_CLASSIFIER:
            current = _DEFAULT_FLASH_CLASSIFIER
            self.flash_classifier = _DEFAULT_FLASH_CLASSIFIER
        return current

    @flash_classifier.setter
    def flash_classifier(self, new_value: str) -> None:
        self.update('flash_classifier', new_value)

    @property
    def flash_classifier_backup(self) -> str:
        return _BACKUP_FLASH_CLASSIFIER

    @property
    def flash_classifier_gpu(self) -> bool:
        return self.get('flash_classifier_gpu', False)

    @flash_classifier_gpu.setter
    def flash_classifier_gpu(self, new_value: bool) -> None:
        self.update('flash_classifier_gpu', new_value)

    @property
    def hollow_zero_event(self) -> str:
        """
        枯萎之都格子模型 只允许使用最新的两个模型
        :return:
        """
        current = self.get('hollow_zero_event', _DEFAULT_HOLLOW_ZERO_EVENT)
        if current!= _DEFAULT_HOLLOW_ZERO_EVENT and current!= _BACKUP_HOLLOW_ZERO_EVENT:
            current = _DEFAULT_HOLLOW_ZERO_EVENT
            self.hollow_zero_event = _DEFAULT_HOLLOW_ZERO_EVENT
        return current

    @hollow_zero_event.setter
    def hollow_zero_event(self, new_value: str) -> None:
        self.update('hollow_zero_event', new_value)

    @property
    def hollow_zero_event_backup(self) -> str:
        return _BACKUP_HOLLOW_ZERO_EVENT

    @property
    def hollow_zero_event_gpu(self) -> bool:
        return self.get('hollow_zero_event_gpu', False)

    @hollow_zero_event_gpu.setter
    def hollow_zero_event_gpu(self, new_value: bool) -> None:
        self.update('hollow_zero_event_gpu', new_value)

    @property
    def lost_void_det(self) -> str:
        """
        迷失之地识别模型 只允许使用最新的两个模型
        :return:
        """
        current = self.get('lost_void_det', _DEFAULT_LOST_VOID_DET)
        if current!= _DEFAULT_LOST_VOID_DET and current!= _BACKUP_LOST_VOID_DET:
            current = _DEFAULT_LOST_VOID_DET
            self.lost_void_det = _DEFAULT_LOST_VOID_DET
        return current

    @lost_void_det.setter
    def lost_void_det(self, new_value: str) -> None:
        self.update('lost_void_det', new_value)

    @property
    def lost_void_det_backup(self) -> str:
        return _BACKUP_LOST_VOID_DET

    @property
    def lost_void_det_gpu(self) -> bool:
        return self.get('lost_void_det_gpu', False)

    @lost_void_det_gpu.setter
    def lost_void_det_gpu(self, new_value: bool) -> None:
        self.update('lost_void_det_gpu', new_value)
