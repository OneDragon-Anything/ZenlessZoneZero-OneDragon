from one_dragon.base.config.yaml_config import YamlConfig

class MirrorChyanConfig(YamlConfig):

    def __init__(self):
        YamlConfig.__init__(self, module_name='mirror_chyan')

    @property
    def cdk(self) -> str:
        """
        获取Mirror酱的CDK
        :return: CDK字符串
        """
        return self.get('cdk', '')

    @cdk.setter
    def cdk(self, new_value: str) -> None:
        """
        设置Mirror酱的CDK
        :return:
        """
        self.update('cdk', new_value)

    @property
    def use_mirror_chyan(self) -> bool:
        """
        是否使用Mirror酱下载资源
        :return: 布尔值，表示是否使用Mirror酱
        """
        return self.get('use_mirror_chyan', False)

    @use_mirror_chyan.setter
    def use_mirror_chyan(self, new_value: bool) -> None:
        """
        设置是否使用Mirror酱下载资源
        :return:
        """
        self.update('use_mirror_chyan', new_value)
