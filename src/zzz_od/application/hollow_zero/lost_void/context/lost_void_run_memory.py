from one_dragon.base.config.yaml_config import YamlConfig
from zzz_od.application.hollow_zero.lost_void.context.lost_void_artifact import (
    LostVoidArtifact,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)


class LostVoidRunMemory(YamlConfig):
    """
    本局记录 本局经过的区域、拿到的藏品、商店刷新和购买
    每次更新都写文件 程序中途重启后接着用 本局结束后清除
    """

    def __init__(self, instance_idx: int, is_mock: bool = False):
        YamlConfig.__init__(self, 'lost_void_run_memory', instance_idx=instance_idx, is_mock=is_mock)

    @property
    def region_list(self) -> list[str]:
        """本局依次进入的区域类型"""
        return self.get('region_list', [])

    @property
    def artifact_list(self) -> list[dict]:
        """本局拿到的藏品 每项含 name category is_gear"""
        return self.get('artifact_list', [])

    @property
    def store_list(self) -> list[dict]:
        """每次进商店一条 含 region refresh_times bought"""
        return self.get('store_list', [])

    @property
    def current_region_type(self) -> str:
        region_list = self.region_list
        return region_list[-1] if len(region_list) > 0 else LostVoidRegionType.ENTRY.value.value

    @property
    def friendly_talk_times(self) -> int:
        return self.region_list.count(LostVoidRegionType.FRIENDLY_TALK.value.value)

    def add_region(self, region_type: str) -> None:
        """
        记录进入的区域 只记区域类型名称 其他交互目标(如感叹号)不记
        """
        if region_type not in [i.value.value for i in LostVoidRegionType]:
            return
        self.update('region_list', self.region_list + [region_type])

    def add_artifact(self, artifact: LostVoidArtifact) -> None:
        item = {'name': artifact.display_name, 'category': artifact.category, 'is_gear': artifact.is_gear}
        self.update('artifact_list', self.artifact_list + [item])

    def start_store(self) -> None:
        item = {'region': self.current_region_type, 'refresh_times': 0, 'bought': []}
        self.update('store_list', self.store_list + [item])

    def add_store_refresh(self) -> None:
        store_list = self.store_list
        if len(store_list) == 0:
            return
        store_list[-1]['refresh_times'] += 1
        self.update('store_list', store_list)

    def add_store_buy(self, name: str) -> None:
        store_list = self.store_list
        if len(store_list) == 0:
            return
        store_list[-1]['bought'].append(name)
        self.update('store_list', store_list)

    def clear(self) -> None:
        """
        本局结束 清空记录并删除文件
        """
        self.data = {}
        self.delete()
