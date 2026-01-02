from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.application.commission_processing import commission_processing_const


class CommissionProcessingConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id=commission_processing_const.APP_ID,
            instance_idx=instance_idx,
            group_id=group_id,
        )
