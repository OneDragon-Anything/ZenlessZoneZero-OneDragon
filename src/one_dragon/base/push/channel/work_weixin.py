import base64
import hashlib
import json

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class WorkWeixin(PushChannel):

    def __init__(self):
        config_schema = [
            PushChannelConfigField(
                var_suffix="ORIGIN",
                title="企业微信代理地址",
                icon="SEND",
                field_type=FieldTypeEnum.TEXT,
                placeholder="可选",
                default='https://qyapi.weixin.qq.com',
            ),
            PushChannelConfigField(
                var_suffix="AM",
                title="企业微信应用",
                icon="APPLICATION",
                field_type=FieldTypeEnum.TEXT,
                placeholder="http://note.youdao.com/s/HMiudGkb"
            ),
            PushChannelConfigField(
                var_suffix="KEY",
                title="企业微信机器人 Key",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="只填 Key"
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='QYWX',
            channel_name='企业微信机器人',
            config_schema=config_schema
        )

    def push(
        self,
        config: dict[str, str],
        title: str,
        content: str,
        image: MatLike | None = None,
        proxy_url: str | None = None,
    ) -> tuple[bool, str]:
        """
        推送消息到企业微信机器人

        Args:
            config: 配置字典，包含 ORIGIN、AM、KEY
            title: 消息标题
            content: 消息内容
            image: 图片数据（可选）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            origin = config.get('ORIGIN', '')
            if len(origin) == 0:
                origin = 'https://qyapi.weixin.qq.com'
            key = config.get('KEY', '')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            url = f"{origin}/cgi-bin/webhook/send?key={key}"
            headers = {"Content-Type": "application/json;charset=utf-8"}

            text_success = False
            image_success = False
            error_messages = []

            # 1. 先发文字
            text_data = {"msgtype": "text", "text": {"content": f"{title}\n{content}"}}
            try:
                resp_obj = requests.post(url, data=json.dumps(text_data), headers=headers, timeout=15)
                resp_obj.raise_for_status()

                status = resp_obj.status_code
                body_snip = (resp_obj.text or "")[:300] if hasattr(resp_obj, "text") else ""
                resp = None

                try:
                    resp = resp_obj.json()
                except Exception as je:
                    error_msg = f"企业微信机器人文字响应解析失败: {type(je).__name__}: {je}; status={status}; body_snip={body_snip}"
                    error_messages.append(error_msg)
                    log.error(error_msg)

                if resp and resp.get("errcode") == 0:
                    text_success = True
                    log.info("企业微信机器人文字推送成功！")
                else:
                    errcode = resp.get("errcode") if resp else None
                    errmsg = resp.get("errmsg") if resp else None
                    error_msg = f"企业微信机器人文字推送失败! status={status}; errcode={errcode}; errmsg={errmsg}; body_snip={body_snip}"
                    error_messages.append(error_msg)
                    log.error(error_msg)
            except Exception as e:
                error_msg = f"企业微信机器人文字推送请求异常: {type(e).__name__}: {e}"
                error_messages.append(error_msg)
                log.error(error_msg)

            # 2. 再发图片
            if image is not None:
                image_success = self._send_image(url, headers, image, error_messages)
            else:
                image_success = True

            # 判断整体结果
            if text_success and image_success:
                return True, "推送成功"
            elif text_success or image_success:
                return True, f"部分推送成功: {'; '.join(error_messages)}" if error_messages else "部分推送成功"
            else:
                return False, f"推送失败: {'; '.join(error_messages)}" if error_messages else "推送失败"

        except Exception as e:
            return False, f"企业微信推送异常: {str(e)}"

    def _send_image(self, url: str, headers: dict[str, str], image: MatLike, error_messages: list[str]) -> bool:
        """
        发送图片到企业微信机器人

        Args:
            url: 机器人URL
            headers: 请求头
            image: 图片数据
            error_messages: 错误消息列表

        Returns:
            bool: 是否发送成功
        """
        # 企业微信机器人图片最大支持2MB
        TARGET_SIZE = 2 * 1024 * 1024
        img_bytes = self.image_to_bytes(image, max_bytes=TARGET_SIZE)
        if img_bytes is None:
            error_msg = "图片转换失败"
            error_messages.append(error_msg)
            log.error(error_msg)
            return False
        img_bytes = img_bytes.getvalue()
        img_size = len(img_bytes)
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        img_md5 = hashlib.md5(img_bytes).hexdigest()
        img_data = {
            "msgtype": "image",
            "image": {"base64": img_base64, "md5": img_md5}
        }

        resp_obj = requests.post(url, data=json.dumps(img_data), headers=headers, timeout=15)
        status = resp_obj.status_code
        body_snip = (resp_obj.text or "")[:300] if hasattr(resp_obj, "text") else ""

        try:
            resp = resp_obj.json()
        except Exception as je:
            error_msg = f"企业微信机器人图片响应解析失败: {type(je).__name__}: {je}; status={status}; body_snip={body_snip}"
            error_messages.append(error_msg)
            log.error(error_msg)
            return False

        if resp and resp.get("errcode") == 0:
            log.info("企业微信机器人图片推送成功！")
            return True
        else:
            errcode = resp.get("errcode") if resp else None
            errmsg = resp.get("errmsg") if resp else None
            error_msg = f"企业微信机器人图片推送失败! status={status}; errcode={errcode}; errmsg={errmsg}; size={img_size}B; body_snip={body_snip}"
            error_messages.append(error_msg)
            log.error(error_msg)
            return False

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证企业微信配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        key = config.get('KEY', '')

        if len(key) == 0:
            return False, "企业微信机器人 Key 不能为空"

        return True, "配置验证通过"