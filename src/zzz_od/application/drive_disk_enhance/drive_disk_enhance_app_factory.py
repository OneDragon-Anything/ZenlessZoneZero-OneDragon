from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.drive_disk_enhance.drive_disk_enhance_const import APP_ID, APP_NAME
from zzz_od.application.drive_disk_enhance.drive_disk_enhance_app import DriveDiskEnhanceApp

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class DriveDiskEnhanceAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=APP_ID,
            app_name=APP_NAME,
            default_group=False,
            need_notify=False,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        """
        创建驱动盘强化应用实例
        
        Args:
            instance_idx: 实例索引
            group_id: 组ID
            
        Returns:
            DriveDiskEnhanceApp 实例
        """
        try:
            app = DriveDiskEnhanceApp(self.ctx)
            print(f"成功创建驱动盘强化应用实例 (实例索引: {instance_idx})")
            return app
        except Exception as e:
            print(f"创建驱动盘强化应用实例失败: {e}")
            raise

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> ApplicationConfig:
        """
        创建应用配置
        
        Args:
            instance_idx: 实例索引
            group_id: 组ID
            
        Returns:
            ApplicationConfig 实例
        """
        config = ApplicationConfig(
            instance_idx=instance_idx,
            group_id=group_id,
        )
        # 可以在这里添加特定于驱动盘强化的配置项
        return config

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        """
        创建运行记录
        
        Args:
            instance_idx: 实例索引
            
        Returns:
            AppRunRecord 实例
        """
        return AppRunRecord(
            app_id=APP_ID,
            instance_idx=instance_idx,
        )
