from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel


class FakePushChannel(PushChannel):

    def __init__(self):
        config_schema = []

        super().__init__(
            channel_id='FAKE',
            channel_name='下面的方法无人维护，遇到问题请自行解决',
            config_schema=config_schema
        )

    def push(
        self,
        config: dict[str, str],
        title: str,
        content: str,
        image: MatLike | None = None
    ) -> tuple[bool, str]:
        """
        推送消息到钉钉机器人

        Args:
            config: 配置字典，包含 SECRET 和 TOKEN
            title: 消息标题
            content: 消息内容
            image: 图片数据（钉钉机器人暂不支持图片推送）

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        return False, '不支持'

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证钉钉机器人配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        return False, '不支持'