"""
企业微信应用推送渠道

提供通过企业微信应用发送文本和图文消息的功能。
需要配置 CorpID, CorpSecret, AgentId，并支持图片上传。
"""

import json
import time
import requests
import threading
from typing import Optional, Tuple

from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class WorkWeixinApp(PushChannel):
    """企业微信应用推送渠道实现类"""

    # 企业微信 API 的默认基础地址
    _BASE_API_URL = "https://qyapi.weixin.qq.com"

    # 存储 Access Token 及其过期时间，用于减少重复请求
    _last_access_token_info: Tuple[str, float] = ("", 0.0)
    _access_token_lock = threading.Lock()

    def __init__(self) -> None:
        """初始化企业微信应用推送渠道"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="CORP_ID",
                title="企业 ID",
                icon="APPLICATION",
                field_type=FieldTypeEnum.TEXT,
                placeholder="企业微信后台 -> 我的企业 -> 企业信息 -> 企业 ID",
                required=True,
            ),
            PushChannelConfigField(
                var_suffix="CORP_SECRET",
                title="应用 Secret",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="企业微信后台 -> 应用管理 -> 自建应用 -> 你的应用 -> Secret",
                required=True,
            ),
            PushChannelConfigField(
                var_suffix="AGENT_ID",
                title="应用 AgentId",
                icon="MESSAGE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="企业微信后台 -> 应用管理 -> 自建应用 -> 你的应用 -> AgentId",
                required=True,
            ),
            PushChannelConfigField(
                var_suffix="TO_USER",
                title="接收者 ID",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="成员ID，多个用 '|' 分隔。默认 @all",
                default="@all",
                required=False,
            ),
            PushChannelConfigField(
                var_suffix="MEDIA_ID",
                title="预设图文封面 Media ID",
                icon="PHOTO",
                field_type=FieldTypeEnum.TEXT,
                placeholder="可选。填写则优先用作图文消息封面。如需动态上传图片，无需填写此项",
                required=False,
            ),
        ]

        PushChannel.__init__(
            self,
            channel_id='QYWX_APP',
            channel_name='企业微信应用',
            config_schema=config_schema
        )

    def _get_access_token(
        self,
        corpid: str,
        corpsecret: str,
        proxies: Optional[dict[str, str]]
    ) -> Tuple[str, str]:
        """
        获取企业微信应用的 access_token，并进行缓存管理。
        access_token 有效期 7200 秒，会提前 300 秒刷新。
        """
        with self._access_token_lock:
            cached_token, expires_at = self._last_access_token_info

            # 如果缓存有效且未临近过期，直接返回
            if cached_token and (expires_at - time.time() > 300):
                return cached_token, ""

            # 获取新的 access_token
            get_token_url = f"{self._BASE_API_URL}/cgi-bin/gettoken" # 直接使用内部常量
            params = {
                "corpid": corpid,
                "corpsecret": corpsecret,
            }
            try:
                response = requests.get(get_token_url, params=params, proxies=proxies, timeout=10)
                response.raise_for_status()
                data = response.json()

                if data.get("errcode") == 0:
                    access_token = data["access_token"]
                    expires_in = data["expires_in"]  # 默认 7200 秒
                    self._last_access_token_info = (access_token, time.time() + expires_in)
                    log.info("企业微信应用 Access Token 获取成功")
                    return access_token, ""
                else:
                    return "", f"获取 Access Token 失败: {data.get('errmsg', '未知错误')}"
            except Exception as e:
                log.error("获取企业微信应用 Access Token 请求异常", exc_info=True)
                return "", f"获取 Access Token 异常: {str(e)}"

    def _upload_image_media(
        self,
        access_token: str,
        image: MatLike,
        proxies: Optional[dict[str, str]]
    ) -> Tuple[str, str]:
        """
        上传图片到企业微信临时素材，获取 media_id。
        临时素材 media_id 在 3 天内有效。
        """
        upload_url = f"{self._BASE_API_URL}/cgi-bin/media/upload?access_token={access_token}&type=image" # 直接使用内部常量
        
        # 企业微信临时素材文件大小限制：图片最大2MB
        TARGET_SIZE = 2 * 1024 * 1024 
        image_bytes_io = self.image_to_bytes(image, max_bytes=TARGET_SIZE)

        if image_bytes_io is None:
            return "", "图片转换或压缩失败"
        
        image_bytes = image_bytes_io.getvalue()

        files = {
            'media': ('image.jpg', image_bytes, 'image/jpeg')
        }
        try:
            response = requests.post(upload_url, files=files, proxies=proxies, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("errcode") == 0:
                log.info(f"企业微信应用图片上传成功，media_id: {data.get('media_id')}")
                return data["media_id"], ""
            else:
                return "", f"图片上传失败: {data.get('errmsg', '未知错误')}"
        except Exception as e:
            log.error("企业微信应用图片上传请求异常", exc_info=True)
            return "", f"图片上传异常: {str(e)}"

    def _send_message_api(
        self,
        access_token: str,
        message_payload: dict,
        proxies: Optional[dict[str, str]]
    ) -> Tuple[bool, str]:
        """封装企业微信发送消息 API 调用"""
        send_url = f"{self._BASE_API_URL}/cgi-bin/message/send?access_token={access_token}" # 直接使用内部常量
        headers = {"Content-Type": "application/json; charset=utf-8"}
        
        try:
            response = requests.post(
                send_url,
                data=json.dumps(message_payload).encode("utf-8"),
                headers=headers,
                proxies=proxies,
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("errcode") == 0:
                return True, "推送成功"
            else:
                return False, f"推送失败: {result.get('errmsg', '未知错误')}"
        except Exception as e:
            log.error("企业微信应用消息发送请求异常", exc_info=True)
            return False, f"消息发送异常: {str(e)}"

    def push(
        self,
        config: dict[str, str],
        title: str,
        content: str,
        image: MatLike | None = None,
        proxy_url: str | None = None,
    ) -> tuple[bool, str]:
        """
        推送消息到企业微信应用

        Args:
            config: 配置字典，包含 CORP_ID、CORP_SECRET、AGENT_ID、TO_USER、MEDIA_ID
            title: 消息标题
            content: 消息内容
            image: 图片数据（可选，将作为图文消息的封面图）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            ok, msg = self.validate_config(config)
            if not ok:
                log.error(f"企业微信应用校验失败：{msg}")
                return False, msg

            corpid = config.get('CORP_ID', '')
            corpsecret = config.get('CORP_SECRET', '')
            agentid = config.get('AGENT_ID', '')
            touser = config.get('TO_USER', '@all')
            pre_configured_media_id = config.get('MEDIA_ID', '')
            # 移除了 origin 的获取，直接使用 _BASE_API_URL

            proxies = self.get_proxy(proxy_url)

            # 1. 获取 Access Token
            access_token, token_err = self._get_access_token(corpid, corpsecret, proxies)
            if not access_token:
                log.error(f"企业微信应用推送失败：{token_err}")
                return False, f"企业微信应用推送失败：{token_err}"

            # 2. 处理图片：如果传入了图片，尝试上传获取 media_id
            effective_media_id_used = False # 标记是否使用了 media_id
            effective_media_id = pre_configured_media_id
            if image is not None:
                uploaded_media_id, upload_err = self._upload_image_media(access_token, image, proxies)
                if uploaded_media_id:
                    effective_media_id = uploaded_media_id
                    effective_media_id_used = True
                    log.info("企业微信应用动态图片成功上传，将以图文消息形式发送。")
                else:
                    log.warning(f"企业微信应用动态图片上传失败，将尝试以文本消息形式发送。错误: {upload_err}")
                    # 如果动态图片上传失败，且没有预设 media_id，则effective_media_id可能为空，这时会走文本消息
                    if not pre_configured_media_id:
                        effective_media_id = "" # 确保在图片上传失败时不会误用旧的media_id
            
            if effective_media_id and not effective_media_id_used: # 如果有预设的media_id，也要将其标记为已使用
                effective_media_id_used = True

            # 3. 构建消息体：根据是否有 effective_media_id 决定发送文本还是图文消息
            message_payload: dict
            if effective_media_id_used: # 判断是否使用 media_id
                # 发送图文消息 (mpnews)
                # 注意: mpnews 的 `content` 字段支持 HTML 标记，这里使用 <br/> 替换换行符
                message_payload = {
                    "touser": touser,
                    "msgtype": "mpnews",
                    "agentid": int(agentid), # AgentId 需要是 int 类型
                    "mpnews": {
                        "articles": [
                            {
                                "title": title,
                                "thumb_media_id": effective_media_id,
                                "author": "OneDragon", # 可自定义
                                "content_source_url": "",  # 可选，可留空
                                "content": content.replace("\n", "<br/>\n"),  # 图文消息内容支持 HTML
                                "digest": content, # 摘要，不含 HTML
                            }
                        ]
                    },
                    "safe": "0", # 是否保密，1 为保密，0 为不保密
                }
            else:
                # 发送文本消息
                message_payload = {
                    "touser": touser,
                    "msgtype": "text",
                    "agentid": int(agentid), # AgentId 需要是 int 类型
                    "text": {"content": f"{title}\n{content}"},
                    "safe": "0",
                }

            # 4. 发送消息
            send_ok, send_msg = self._send_message_api(access_token, message_payload, proxies)

            # 如果图文消息发送失败，尝试回退到文本消息（仅当原意是发送图文且发送失败时）
            if not send_ok and effective_media_id_used:
                log.warning(f"企业微信应用图文消息发送失败：{send_msg}，尝试发送纯文本消息。")
                text_fallback_payload = {
                    "touser": touser,
                    "msgtype": "text",
                    "agentid": int(agentid),
                    "text": {"content": f"{title}\n{content}"},
                    "safe": "0",
                }
                text_fallback_ok, text_fallback_msg = self._send_message_api(
                    access_token, text_fallback_payload, proxies
                )
                if text_fallback_ok:
                    log.info("企业微信应用图文消息失败，已回退至文本消息推送成功")
                    return True, "图文消息失败，已回退至文本消息推送成功"
                else:
                    log.error(f"企业微信应用图文消息和文本消息均失败: {send_msg}; 文本回退失败: {text_fallback_msg}")
                    return False, f"图文消息和文本消息均失败: {send_msg}; 文本回退失败: {text_fallback_msg}"
            
            return send_ok, send_msg

        except Exception as e:
            log.error("企业微信应用推送异常", exc_info=True)
            return False, f"企业微信应用推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证企业微信应用配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        corpid = config.get('CORP_ID', '')
        corpsecret = config.get('CORP_SECRET', '')
        agentid = config.get('AGENT_ID', '')

        if not corpid.strip():
            return False, "企业 ID 不能为空"
        if not corpsecret.strip():
            return False, "应用 Secret 不能为空"
        if not agentid.strip():
            return False, "应用 AgentId 不能为空"
        # 验证 AgentId 是否为有效数字
        try:
            int(agentid)
        except ValueError:
            return False, "应用 AgentId 必须是有效的数字"

        return True, "配置验证通过"

