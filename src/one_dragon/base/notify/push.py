# 代码来自whyour/qinglong/develop/sample/notify.py, 感谢原作者的贡献
from __future__ import annotations

import base64
import datetime
import functools
import hashlib
import hmac
import json
import re
import smtplib
import threading
import time
import urllib.parse
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from io import BytesIO
from typing import TYPE_CHECKING, Optional

import requests

from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext

def track_push_method(func):
    """装饰器：自动为推送方法添加遥测功能"""
    @functools.wraps(func)
    def wrapper(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        method_name = func.__name__

        try:
            # 执行原始推送方法
            result = func(self, title, content, image)

            # 如果方法执行完成没有抛出异常，记录成功
            # 注意：具体的成功/失败判断由各个方法内部处理
            # 装饰器只处理未捕获的异常
            return result

        except Exception as e:
            # 记录推送失败
            if hasattr(self, '_track_push_failure'):
                self._track_push_failure(method_name, str(e))
            raise

    return wrapper

class Push():

    def __init__(self, ctx: OneDragonContext):
        self.ctx: OneDragonContext = ctx



    def bark(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 Bark 推送消息。
        """

        self.log_info("Bark 服务启动")

        bark_push = self.get_config("BARK_PUSH")
        if bark_push.startswith("http"):
            url = f'{bark_push}'
        else:
            url = f'https://api.day.app/{bark_push}'

        data = {
            "title": title,
            "body": content,
        }

        # 添加可选参数
        if self.get_config("BARK_ARCHIVE"):
            data["isArchive"] = self.get_config("BARK_ARCHIVE")
        if self.get_config("BARK_GROUP"):
            data["group"] = self.get_config("BARK_GROUP")
        if self.get_config("BARK_SOUND"):
            data["sound"] = self.get_config("BARK_SOUND")
        if self.get_config("BARK_ICON"):
            data["icon"] = self.get_config("BARK_ICON")
        if self.get_config("BARK_LEVEL"):
            data["level"] = self.get_config("BARK_LEVEL")
        if self.get_config("BARK_URL"):
            data["url"] = self.get_config("BARK_URL")
        headers = {"Content-Type": "application/json;charset=utf-8"}

        try:
            response = requests.post(
                url=url, data=json.dumps(data), headers=headers, timeout=15
            ).json()

            if response["code"] == 200:
                self.log_info("Bark 推送成功！")
            else:
                self.log_error("Bark 推送失败！")
        except Exception as e:
            self.log_error(f"Bark 推送异常: {e}")



    def console(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 控制台 推送消息。
        """
        print(f"{title}\n{content}")



    def dingding_bot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 钉钉机器人 推送消息。
        """

        self.log_info("钉钉机器人 服务启动")

        timestamp = str(round(time.time() * 1000))
        secret = self.get_config("DD_BOT_SECRET")
        secret_enc = secret.encode("utf-8")
        string_to_sign = "{}\n{}".format(timestamp, secret)
        string_to_sign_enc = string_to_sign.encode("utf-8")
        hmac_code = hmac.new(
            secret_enc, string_to_sign_enc, digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        url = f'https://oapi.dingtalk.com/robot/send?access_token={self.get_config("DD_BOT_TOKEN")}&timestamp={timestamp}&sign={sign}'
        headers = {"Content-Type": "application/json;charset=utf-8"}
        data = {"msgtype": "text", "text": {"content": f"{title}\n{content}"}}

        try:
            response = requests.post(
                url=url, data=json.dumps(data), headers=headers, timeout=15
            ).json()

            if not response["errcode"]:
                self.log_info("钉钉机器人 推送成功！")
            else:
                self.log_error("钉钉机器人 推送失败！")
        except Exception as e:
            self.log_error(f"钉钉机器人 推送异常: {e}")



    def feishu_bot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 飞书机器人 推送消息。
        """

        self.log_info("飞书 服务启动")

        channel = self.get_config("FS_CHANNEL")
        base_url = "open.feishu.cn" if channel == "飞书" else "open.larksuite.com"

        app_id = self.get_config("FS_APPID")
        app_secret = self.get_config("FS_APPSECRET")
        if image and app_id and app_secret and app_id != "" and app_secret != "":
            image.seek(0)
            # 获取飞书自建应用的tenant_access_token
            auth_endpoint = f"https://{base_url}/open-apis/auth/v3/tenant_access_token/internal"
            auth_headers = {
                "Content-Type": "application/json; charset=utf-8"
            }
            auth_response = requests.post(auth_endpoint, headers=auth_headers, json={
                "app_id": app_id,
                "app_secret": app_secret
            })
            auth_response.raise_for_status()
            tenant_access_token = auth_response.json()["tenant_access_token"]
            # 上传图片并获取图片的image_key
            image_endpoint = f"https://{base_url}/open-apis/im/v1/images"
            image_headers = {
                "Authorization": f"Bearer {tenant_access_token}"
            }
            files = {
                'image': ('image.jpg', image.getvalue(), 'image/jpeg'),
                'image_type': (None, 'message')
            }
            image_response = requests.post(image_endpoint , headers=image_headers, files=files)
            if (image_response.status_code % 100 != 2):
                log.error(image_response.text)
                image_response.raise_for_status()
            image_key = image_response.json()["data"]["image_key"]
        else:
            image_key = None

        if image_key:
            data = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": title,
                            "content": [
                                [{
                                    "tag": "text",
                                    "text": f"{content}"
                                }, {
                                    "tag": "img",
                                    "image_key": image_key
                                }]
                            ]
                        }
                    }
                }
            }
        else:
            data = {
                "msg_type": "text",
                "content": {"text": f"{title}\n{content}"}
            }

        url = f'https://{base_url}/open-apis/bot/v2/hook/{self.get_config("FS_KEY")}'
        response = requests.post(url, data=json.dumps(data)).json()

        if response.get("StatusCode") == 0 or response.get("code") == 0:
            self.log_info("飞书 推送成功！")
        else:
            self.log_error(f"飞书 推送失败！错误信息如下：\n{response}")



    def one_bot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 OneBot 推送消息。
        """

        self.log_info("OneBot 服务启动")

        url = self.get_config("ONEBOT_URL")
        user_id = self.get_config("ONEBOT_USER")
        group_id = self.get_config("ONEBOT_GROUP")
        token = self.get_config("ONEBOT_TOKEN")

        if url:
            url = url.rstrip("/")
            url += "" if url.endswith("/send_msg") else "/send_msg"

        headers = {'Content-Type': "application/json"}
        message = [{"type": "text", "data": {"text": f"{title}\n{content}"}}]
        if image:
            image.seek(0)
            image_base64 = base64.b64encode(image.getvalue()).decode('utf-8')
            message.append({"type": "image", "data": {"file": f'base64://{image_base64}'}})
        data_private = {"message": message}
        data_group = {"message": message}

        if token != "":
            headers["Authorization"] = f"Bearer {token}"

        if user_id != "":
            data_private["message_type"] = "private"
            data_private["user_id"] = user_id
            response_private = requests.post(url, data=json.dumps(data_private), headers=headers).json()

            if response_private["status"] == "ok":
                self.log_info("OneBot 私聊推送成功！")
            else:
                self.log_error("OneBot 私聊推送失败！")

        if group_id != "":
            data_group["message_type"] = "group"
            data_group["group_id"] = group_id
            response_group = requests.post(url, data=json.dumps(data_group), headers=headers).json()

            if response_group["status"] == "ok":
                self.log_info("OneBot 群聊推送成功！")
            else:
                self.log_error("OneBot 群聊推送失败！")



    def gotify(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 gotify 推送消息。
        """

        self.log_info("gotify 服务启动")

        url = f'{self.get_config("GOTIFY_URL")}/message?token={self.get_config("GOTIFY_TOKEN")}'
        data = {
            "title": title,
            "message": content,
            "priority": self.get_config("GOTIFY_PRIORITY"),
        }
        response = requests.post(url, data=data).json()

        if response.get("id"):
            self.log_info("gotify 推送成功！")
        else:
            self.log_error("gotify 推送失败！")



    def iGot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 iGot 推送消息。
        """

        self.log_info("iGot 服务启动")

        url = f'https://push.hellyw.com/{self.get_config("IGOT_PUSH_KEY")}'
        data = {"title": title, "content": content}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(url, data=data, headers=headers).json()

        if response["ret"] == 0:
            self.log_info("iGot 推送成功！")
        else:
            self.log_error(f'iGot 推送失败！{response["errMsg"]}')



    def serverchan(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        通过 ServerChan 推送消息。
        """

        self.log_info("Server 酱 服务启动")

        data = {"text": title, "desp": content.replace("\n", "\n\n")}

        match = re.match(r"sctp(\d+)t", self.get_config("SERVERCHAN_PUSH_KEY"))
        if match:
            num = match.group(1)
            url = f'https://{num}.push.ft07.com/send/{self.get_config("SERVERCHAN_PUSH_KEY")}.send'
        else:
            url = f'https://sctapi.ftqq.com/{self.get_config("SERVERCHAN_PUSH_KEY")}.send'

        response = requests.post(url, data=data).json()

        if response.get("errno") == 0 or response.get("code") == 0:
            self.log_info("Server 酱 推送成功！")
        else:
            self.log_error(f'Server 酱 推送失败！错误码：{response["message"]}')



    def pushdeer(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        通过PushDeer 推送消息
        """

        self.log_info("PushDeer 服务启动")
        data = {
            "text": title,
            "desp": content,
            "type": "markdown",
            "pushkey": self.get_config("DEER_KEY"),
        }
        url = "https://api2.pushdeer.com/message/push"
        if self.get_config("DEER_URL"):
            url = self.get_config("DEER_URL")

        response = requests.post(url, data=data).json()

        if len(response.get("content").get("result")) > 0:
            self.log_info("PushDeer 推送成功！")
        else:
            self.log_error(f"PushDeer 推送失败！错误信息：{response}")



    def chat(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        通过Chat 推送消息
        """

        self.log_info("chat 服务启动")
        data = "payload=" + json.dumps({"text": title + "\n" + content})
        url = self.get_config("CHAT_URL") + self.get_config("CHAT_TOKEN")
        response = requests.post(url, data=data)

        if response.status_code == 200:
            self.log_info("Chat 推送成功！")
            self._track_push_success('chat')
        else:
            self.log_error(f"Chat 推送失败！错误信息：{response}")
            self._track_push_failure('chat', f"Status code: {response.status_code}")



    def pushplus_bot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        通过 pushplus 推送消息。
        """

        self.log_info("PUSHPLUS 服务启动")

        url = "https://www.pushplus.plus/send"
        data = {
            "token": self.get_config("PUSH_PLUS_TOKEN"),
            "title": title,
            "content": content,
            "topic": self.get_config("PUSH_PLUS_USER"),
            "template": self.get_config("PUSH_PLUS_TEMPLATE"),
            "channel": self.get_config("PUSH_PLUS_CHANNEL"),
            "webhook": self.get_config("PUSH_PLUS_WEBHOOK"),
            "callbackUrl": self.get_config("PUSH_PLUS_CALLBACKURL"),
            "to": self.get_config("PUSH_PLUS_TO"),
        }
        body = json.dumps(data).encode(encoding="utf-8")
        headers = {"Content-Type": "application/json"}
        response = requests.post(url=url, data=body, headers=headers).json()

        code = response["code"]
        if code == 200:
            self.log_info("PUSHPLUS 推送请求成功，可根据流水号查询推送结果:" + response["data"])
            self.log_info(
                "注意：请求成功并不代表推送成功，如未收到消息，请到pushplus官网使用流水号查询推送最终结果"
            )
        elif code == 900 or code == 903 or code == 905 or code == 999:
            self.log_info(response["msg"])

        else:
            url_old = "http://pushplus.hxtrip.com/send"
            headers["Accept"] = "application/json"
            response = requests.post(url=url_old, data=body, headers=headers).json()

            if response["code"] == 200:
                self.log_info("PUSHPLUS(hxtrip) 推送成功！")

            else:
                self.log_error("PUSHPLUS 推送失败！")



    def weplus_bot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        通过 微加机器人 推送消息。
        """

        self.log_info("微加机器人 服务启动")

        template = "txt"
        if len(content) > 800:
            template = "html"

        url = "https://www.weplusbot.com/send"
        data = {
            "token": self.get_config("WE_PLUS_BOT_TOKEN"),
            "title": title,
            "content": content,
            "template": template,
            "receiver": self.get_config("WE_PLUS_BOT_RECEIVER"),
            "version": self.get_config("WE_PLUS_BOT_VERSION"),
        }
        body = json.dumps(data).encode(encoding="utf-8")
        headers = {"Content-Type": "application/json"}
        response = requests.post(url=url, data=body, headers=headers).json()

        if response["code"] == 200:
            self.log_info("微加机器人 推送成功！")
        else:
            self.log_error("微加机器人 推送失败！")



    def qmsg_bot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 qmsg 推送消息。
        """

        self.log_info("qmsg 服务启动")

        url = f'https://qmsg.zendee.cn/{self.get_config("QMSG_TYPE")}/{self.get_config("QMSG_KEY")}'
        payload = {"msg": f'{title}\n{content.replace("----", "-")}'.encode("utf-8")}
        response = requests.post(url=url, params=payload).json()

        if response["code"] == 0:
            self.log_info("qmsg 推送成功！")
        else:
            self.log_error(f'qmsg 推送失败！{response["reason"]}')



    def wecom_app(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        通过 企业微信 APP 推送消息。
        """
        QYWX_AM_AY = re.split(",", self.get_config("QYWX_AM"))
        if 4 < len(QYWX_AM_AY) > 5:
            self.log_info("QYWX_AM 设置错误!!")
            return
        self.log_info("企业微信 APP 服务启动")

        corpid = QYWX_AM_AY[0]
        corpsecret = QYWX_AM_AY[1]
        touser = QYWX_AM_AY[2]
        agentid = QYWX_AM_AY[3]
        try:
            media_id = QYWX_AM_AY[4]
        except IndexError:
            media_id = ""
        if self.get_config("QYWX_ORIGIN"):
            origin = self.get_config("QYWX_ORIGIN")
        else:
            origin = "https://qyapi.weixin.qq.com"
        wx = self.WeCom(corpid, corpsecret, agentid, origin)
        # 如果没有配置 media_id 默认就以 text 方式发送
        if not media_id:
            message = title + "\n\n" + content
            response = wx.send_text(message, touser)
        else:
            response = wx.send_mpnews(title, content, media_id, touser)

        if response == "ok":
            self.log_info("企业微信推送成功！")
        else:
            self.log_error(f"企业微信推送失败！错误信息如下：\n{response}")


    class WeCom:
        def __init__(self, corpid, corpsecret, agentid, origin):
            self.CORPID = corpid
            self.CORPSECRET = corpsecret
            self.AGENTID = agentid
            self.ORIGIN = origin

        def get_access_token(self):
            url = f"{self.ORIGIN}/cgi-bin/gettoken"
            values = {
                "corpid": self.CORPID,
                "corpsecret": self.CORPSECRET,
            }
            req = requests.post(url, params=values)
            data = json.loads(req.text)
            return data["access_token"]

        def send_text(self, message, touser="@all"):
            send_url = (
                f"{self.ORIGIN}/cgi-bin/message/send?access_token={self.get_access_token()}"
            )
            send_values = {
                "touser": touser,
                "msgtype": "text",
                "agentid": self.AGENTID,
                "text": {"content": message},
                "safe": "0",
            }
            send_msges = bytes(json.dumps(send_values), "utf-8")
            respone = requests.post(send_url, send_msges)
            respone = respone.json()
            return respone["errmsg"]

        def send_mpnews(self, title, message, media_id, touser="@all"):
            send_url = (
                f"{self.ORIGIN}/cgi-bin/message/send?access_token={self.get_access_token()}"
            )
            send_values = {
                "touser": touser,
                "msgtype": "mpnews",
                "agentid": self.AGENTID,
                "mpnews": {
                    "articles": [
                        {
                            "title": title,
                            "thumb_media_id": media_id,
                            "author": "Author",
                            "content_source_url": "",
                            "content": message.replace("\n", "<br/>"),
                            "digest": message,
                        }
                    ]
                },
            }
            send_msges = bytes(json.dumps(send_values), "utf-8")
            respone = requests.post(send_url, send_msges)
            respone = respone.json()
            return respone["errmsg"]



    def wecom_bot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        通过 企业微信机器人 推送消息
        文本与图片分开发送, 图片需base64+md5, 大小≤2MB
        图片若为JPG/PNG且大小≤2MB直接发送; 若格式不符或超过2MB, 则统一转为JPG格式后发送
        """
        self.log_info("企业微信机器人服务启动")

        origin = self.get_config("QYWX_ORIGIN", "https://qyapi.weixin.qq.com")

        url = f"{origin}/cgi-bin/webhook/send?key={self.get_config('QYWX_KEY')}"
        headers = {"Content-Type": "application/json;charset=utf-8"}

        # 1. 先发文字
        text_data = {"msgtype": "text", "text": {"content": f"{title}\n{content}"}}
        try:
            resp_obj = requests.post(url, data=json.dumps(text_data), headers=headers, timeout=15)
        except requests.RequestException as e:
            self.log_error(f"企业微信机器人文字推送请求异常: {type(e).__name__}: {e}")
        else:
            status = getattr(resp_obj, "status_code", None)
            body_snip = (resp_obj.text or "")[:300] if hasattr(resp_obj, "text") else ""
            resp = None
            try:
                resp = resp_obj.json()
            except ValueError as je:
                self.log_error(f"企业微信机器人文字响应解析失败: {type(je).__name__}: {je}; status={status}; body_snip={body_snip}")
            if resp and resp.get("errcode") == 0:
                self.log_info("企业微信机器人文字推送成功！")
            else:
                errcode = resp.get("errcode") if resp else None
                errmsg = resp.get("errmsg") if resp else None
                self.log_error(
                    f"企业微信机器人文字推送失败!status={status}; errcode={errcode}; errmsg={errmsg}; body_snip={body_snip}"
                )

        # 2. 再发图片
        if image:
            # 企业微信机器人图片最大支持2MB
            TARGET_SIZE = 2 * 1024 * 1024

            image.seek(0)
            img_bytes = image.getvalue()
            orig_size = len(img_bytes)
            if len(img_bytes) <= TARGET_SIZE:
                # 直接发送，传入图片为png格式，大小≤2MB, 无需压缩
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                img_md5 = hashlib.md5(img_bytes).hexdigest()
                img_data = {
                    "msgtype": "image",
                    "image": {"base64": img_base64, "md5": img_md5}
                }
                try:
                    resp_obj = requests.post(url, data=json.dumps(img_data), headers=headers, timeout=15)
                except requests.RequestException as e:
                    self.log_error(f"企业微信机器人图片推送请求异常(直发): {type(e).__name__}: {e}; size={orig_size}B")
                else:
                    status = getattr(resp_obj, "status_code", None)
                    body_snip = (resp_obj.text or "")[:300] if hasattr(resp_obj, "text") else ""
                    resp = None
                    try:
                        resp = resp_obj.json()
                    except ValueError as je:
                        self.log_error(f"企业微信机器人图片响应解析失败(直发): {type(je).__name__}: {je}; status={status}; body_snip={body_snip}")
                    if resp and resp.get("errcode") == 0:
                        self.log_info("企业微信机器人图片推送成功！(无需压缩)")
                    else:
                        errcode = resp.get("errcode") if resp else None
                        errmsg = resp.get("errmsg") if resp else None
                        self.log_error(
                            f"企业微信机器人图片推送失败(直发)! status={status}; errcode={errcode}; errmsg={errmsg}; size={orig_size}B; body_snip={body_snip}"
                        )
            else:
                try:
                    img_bytes_c, _, quality = self._compress_image(image, TARGET_SIZE)
                except Exception as e:
                    self.log_error(f"图片处理失败, 未发送图片! orig_size={orig_size}B")
                    return
                if len(img_bytes_c) > TARGET_SIZE:
                    self.log_error(f"图片压缩后仍超过2MB,未发送图片! orig_size={orig_size}B; compressed_size={len(img_bytes_c)}B")
                    return
                img_base64 = base64.b64encode(img_bytes_c).decode('utf-8')
                img_md5 = hashlib.md5(img_bytes_c).hexdigest()
                img_data = {
                    "msgtype": "image",
                    "image": {"base64": img_base64, "md5": img_md5}
                }
                try:
                    resp_obj = requests.post(url, data=json.dumps(img_data), headers=headers, timeout=15)
                except requests.RequestException as e:
                    self.log_error(f"企业微信机器人图片推送请求异常(压缩): {type(e).__name__}: {e}; orig_size={orig_size}B; compressed_size={len(img_bytes_c)}B")
                else:
                    status = getattr(resp_obj, "status_code", None)
                    body_snip = (resp_obj.text or "")[:300] if hasattr(resp_obj, "text") else ""
                    resp = None
                    try:
                        resp = resp_obj.json()
                    except ValueError as je:
                        self.log_error(f"企业微信机器人图片响应解析失败(压缩): {type(je).__name__}: {je}; status={status}; body_snip={body_snip}")
                    if resp and resp.get("errcode") == 0:
                        self.log_info(f"企业微信机器人图片推送成功！(压缩质量 {quality})")
                    else:
                        errcode = resp.get("errcode") if resp else None
                        errmsg = resp.get("errmsg") if resp else None
                        self.log_error(
                            f"企业微信机器人图片推送失败(压缩)! status={status}; errcode={errcode}; errmsg={errmsg}; orig_size={orig_size}B; compressed_size={len(img_bytes_c)}B; body_snip={body_snip}"
                        )



    def discord_bot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 Discord Bot 推送消息。
        """

        self.log_info("Discord Bot 服务启动")

        base_url = "https://discord.com/api/v9"
        headers = {
            "Authorization": f"Bot {self.get_config('DISCORD_BOT_TOKEN')}",
            "User-Agent": "OneDragon"
        }

        create_dm_url = f"{base_url}/users/@me/channels"
        dm_headers = headers.copy()
        dm_headers["Content-Type"] = "application/json"
        dm_payload = json.dumps({"recipient_id": self.get_config('DISCORD_USER_ID')})
        response = requests.post(create_dm_url, headers=dm_headers, data=dm_payload, timeout=15)
        response.raise_for_status()
        channel_id = response.json().get("id")
        if not channel_id or channel_id == "":
            self.log_error(f"Discord 私聊频道建立失败")
            return

        message_url = f"{base_url}/channels/{channel_id}/messages"
        message_payload_dict = {"content": f"{title}\n{content}"}

        files = None
        if image:
            image.seek(0)
            files = {'file': ('image.png', image, 'image/png')}
            data = {'payload_json': json.dumps(message_payload_dict)}
            if "Content-Type" in headers:
                del headers["Content-Type"]
        else:
            headers["Content-Type"] = "application/json"
            data = json.dumps(message_payload_dict)

        response = requests.post(message_url, headers=headers, data=data, files=files, timeout=30)
        response.raise_for_status()
        self.log_info("Discord Bot 推送成功！")



    def telegram_bot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 telegram 机器人 推送消息。
        """

        self.log_info("Telegram 服务启动")

        proxies = None
        if self.get_config("TG_PROXY_HOST") and self.get_config("TG_PROXY_PORT"):
            if self.get_config("TG_PROXY_AUTH") != "" and "@" not in self.get_config(
                "TG_PROXY_HOST"
            ):
                self.push_config["TG_PROXY_HOST"] = (
                    self.get_config("TG_PROXY_AUTH")
                    + "@"
                    + self.get_config("TG_PROXY_HOST")
                )
            proxyStr = "http://{}:{}".format(
                self.get_config("TG_PROXY_HOST"), self.get_config("TG_PROXY_PORT")
            )
            proxies = {"http": proxyStr, "https": proxyStr}

        if self.get_config("TG_API_HOST"):
            url = f"{self.get_config('TG_API_HOST')}/bot{self.get_config('TG_BOT_TOKEN')}/sendMessage"
            photo_url = f"{self.get_config('TG_API_HOST')}/bot{self.get_config('TG_BOT_TOKEN')}/sendPhoto"
        else:
            url = (
                f"https://api.telegram.org/bot{self.get_config('TG_BOT_TOKEN')}/sendMessage"
            )
            photo_url = f"https://api.telegram.org/bot{self.get_config('TG_BOT_TOKEN')}/sendPhoto"

        if image:
            # 发送图片
            image.seek(0)
            files = {
                'photo': ('image.jpg', image.getvalue(), 'image/jpeg'),
                'chat_id': (None, str(self.get_config("TG_USER_ID"))),
                'caption': (None, f"{title}\n{content}")
            }
            response = requests.post(photo_url, files=files, proxies=proxies).json()
        else:
            # 发送消息
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            payload = {
                "chat_id": str(self.get_config("TG_USER_ID")),
                "text": f"{title}\n{content}",
            }

            response = requests.post(
                url=url, headers=headers, params=payload, proxies=proxies
            ).json()

        if response["ok"]:
            self.log_info("Telegram 推送成功！")
        else:
            self.log_error("Telegram 推送失败！")



    def aibotk(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 智能微秘书 推送消息。
        """

        self.log_info("智能微秘书 服务启动")

        if self.get_config("AIBOTK_TYPE") == "room":
            url = "https://api-bot.aibotk.com/openapi/v1/chat/room"
            data = {
                "apiKey": self.get_config("AIBOTK_KEY"),
                "roomName": self.get_config("AIBOTK_NAME"),
                "message": {"type": 1, "content": f"{title}\n{content}"},
            }
        else:
            url = "https://api-bot.aibotk.com/openapi/v1/chat/contact"
            data = {
                "apiKey": self.get_config("AIBOTK_KEY"),
                "name": self.get_config("AIBOTK_NAME"),
                "message": {"type": 1, "content": f"{title}\n{content}"},
            }
        body = json.dumps(data).encode(encoding="utf-8")
        headers = {"Content-Type": "application/json"}
        response = requests.post(url=url, data=body, headers=headers).json()
        if response["code"] == 0:
            self.log_info("智能微秘书 推送成功！")
        else:
            self.log_error(f'智能微秘书 推送失败！{response["error"]}')



    def smtp(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 SMTP 邮件 推送消息。
        """

        self.log_info("SMTP 邮件 服务启动")

        message = MIMEText(content, "plain", "utf-8")
        message["From"] = formataddr(
            (
                Header(self.get_config("SMTP_NAME"), "utf-8").encode(),
                self.get_config("SMTP_EMAIL"),
            )
        )
        message["To"] = formataddr(
            (
                Header(self.get_config("SMTP_NAME"), "utf-8").encode(),
                self.get_config("SMTP_EMAIL"),
            )
        )
        message["Subject"] = Header(title, "utf-8")

        try:
            smtp_server = (
                smtplib.SMTP_SSL(self.get_config("SMTP_SERVER"))
                if self.get_config("SMTP_SSL") == "true"
                else smtplib.SMTP(self.get_config("SMTP_SERVER"))
            )
            if self.get_config("SMTP_STARTTLS") == "true":
                smtp_server.starttls()
            smtp_server.login(
                self.get_config("SMTP_EMAIL"), self.get_config("SMTP_PASSWORD")
            )
            smtp_server.sendmail(
                self.get_config("SMTP_EMAIL"),
                self.get_config("SMTP_EMAIL"),
                message.as_bytes(),
            )
            smtp_server.close()
            self.log_info("SMTP 邮件 推送成功！")
        except Exception as e:
            self.log_error(f"SMTP 邮件 推送失败！{e}")



    def pushme(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 PushMe 推送消息。
        """

        self.log_info("PushMe 服务启动")

        url = (
            self.get_config("PUSHME_URL")
            if self.get_config("PUSHME_URL")
            else "https://push.i-i.me/"
        )
        data = {
            "push_key": self.get_config("PUSHME_KEY"),
            "title": title,
            "content": content,
            "date": self.get_config("date") if self.get_config("date") else "",
            "type": self.get_config("type") if self.get_config("type") else "",
        }
        response = requests.post(url, data=data)

        if response.status_code == 200 and response.text == "success":
            self.log_info("PushMe 推送成功！")
        else:
            self.log_error(f"PushMe 推送失败！{response.status_code} {response.text}")



    def chronocat(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        使用 CHRONOCAT 推送消息。
        """

        self.log_info("CHRONOCAT 服务启动")

        user_ids = re.findall(r"user_id=(\d+)", self.get_config("CHRONOCAT_QQ"))
        group_ids = re.findall(r"group_id=(\d+)", self.get_config("CHRONOCAT_QQ"))

        url = f'{self.get_config("CHRONOCAT_URL")}/api/message/send'
        headers = {
            "Content-Type": "application/json",
            "Authorization": f'Bearer {self.get_config("CHRONOCAT_TOKEN")}',
        }

        for chat_type, ids in [(1, user_ids), (2, group_ids)]:
            if not ids:
                continue
            for chat_id in ids:
                data = {
                    "peer": {"chatType": chat_type, "peerUin": chat_id},
                    "elements": [
                        {
                            "elementType": 1,
                            "textElement": {"content": f"{title}\n{content}"},
                        }
                    ],
                }
                response = requests.post(url, headers=headers, data=json.dumps(data))
                if response.status_code == 200:
                    if chat_type == 1:
                        self.log_info(f"QQ个人消息:{ids}推送成功！")
                    else:
                        self.log_info(f"QQ群消息:{ids}推送成功！")
                else:
                    if chat_type == 1:
                        self.log_error(f"QQ个人消息:{ids}推送失败！")
                    else:
                        self.log_error(f"QQ群消息:{ids}推送失败！")



    def ntfy(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        通过 Ntfy 推送消息
        """

        def encode_rfc2047(text: str) -> str:
            """将文本编码为符合 RFC 2047 标准的格式"""
            encoded_bytes = base64.b64encode(text.encode("utf-8"))
            encoded_str = encoded_bytes.decode("utf-8")
            return f"=?utf-8?B?{encoded_str}?="

        self.log_info("ntfy 服务启动")
        priority = "3"
        if not self.get_config("NTFY_PRIORITY"):
            self.log_info("ntfy 服务的NTFY_PRIORITY 未设置!!默认设置为3")
        else:
            priority = self.get_config("NTFY_PRIORITY")

        # 使用 RFC 2047 编码 title
        encoded_title = encode_rfc2047(title)

        data = content.encode(encoding="utf-8")
        headers = {"Title": encoded_title, "Priority": priority}  # 使用编码后的 title

        if self.get_config("NTFY_TOKEN"):
            headers['Authorization'] = "Bearer " + self.get_config("NTFY_TOKEN")
        elif self.get_config("NTFY_USERNAME") and self.get_config("NTFY_PASSWORD"):
            authStr = self.get_config("NTFY_USERNAME") + ":" + self.get_config("NTFY_PASSWORD")
            headers['Authorization'] = "Basic " + base64.b64encode(authStr.encode('utf-8')).decode('utf-8')
        if self.get_config("NTFY_ACTIONS"):
            headers['Actions'] = encode_rfc2047(self.get_config("NTFY_ACTIONS"))

        url = self.get_config("NTFY_URL") + "/" + self.get_config("NTFY_TOPIC")
        response = requests.post(url, data=data, headers=headers)
        if response.status_code == 200:  # 使用 response.status_code 进行检查
            self.log_info("Ntfy 推送成功！")
        else:
            self.log_error(f"Ntfy 推送失败！错误信息：{response.text}")



    def wxpusher_bot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        通过 wxpusher 推送消息。
        支持的环境变量:
        - WXPUSHER_APP_TOKEN: appToken
        - WXPUSHER_TOPIC_IDS: 主题ID, 多个用英文分号;分隔
        - WXPUSHER_UIDS: 用户ID, 多个用英文分号;分隔
        """

        url = "https://wxpusher.zjiecode.com/api/send/message"

        # 处理topic_ids和uids，将分号分隔的字符串转为数组
        topic_ids = []
        if self.get_config("WXPUSHER_TOPIC_IDS"):
            topic_ids = [
                int(id.strip())
                for id in self.get_config("WXPUSHER_TOPIC_IDS").split(";")
                if id.strip()
            ]

        uids = []
        if self.get_config("WXPUSHER_UIDS"):
            uids = [
                uid.strip()
                for uid in self.get_config("WXPUSHER_UIDS").split(";")
                if uid.strip()
            ]

        # topic_ids uids 至少有一个
        if not topic_ids and not uids:
            self.log_info("wxpusher 服务的 WXPUSHER_TOPIC_IDS 和 WXPUSHER_UIDS 至少设置一个!!")
            return

        self.log_info("wxpusher 服务启动")

        data = {
            "appToken": self.get_config("WXPUSHER_APP_TOKEN"),
            "content": f"<h1>{title}</h1><br/><div style='white-space: pre-wrap;'>{content}</div>",
            "summary": title,
            "contentType": 2,
            "topicIds": topic_ids,
            "uids": uids,
            "verifyPayType": 0,
        }

        headers = {"Content-Type": "application/json"}
        response = requests.post(url=url, json=data, headers=headers).json()

        if response.get("code") == 1000:
            self.log_info("wxpusher 推送成功！")
        else:
            self.log_error(f"wxpusher 推送失败！错误信息：{response.get('msg')}")


    def webhook_bot(self, title: str, content: str, image: Optional[BytesIO]) -> None:
        """
        通过通用 Webhook 推送消息
        """
        self.log_info("通用 Webhook 服务启动")

        url = self.get_config("WEBHOOK_URL")
        method = self.get_config("WEBHOOK_METHOD")
        headers_str = self.get_config("WEBHOOK_HEADERS")
        body = self.get_config("WEBHOOK_BODY")
        content_type = self.get_config("WEBHOOK_CONTENT_TYPE")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        iso_timestamp = datetime.datetime.now().isoformat()
        unix_timestamp = str(int(time.time()))

        # 变量替换
        replacements = {
            "$title": title, "{{title}}": title,
            "$content": content, "{{content}}": content,
            "$timestamp": timestamp, "{{timestamp}}": timestamp,
            "$iso_timestamp": iso_timestamp, "{{iso_timestamp}}": iso_timestamp,
            "$unix_timestamp": unix_timestamp, "{{unix_timestamp}}": unix_timestamp,
        }

        for placeholder, value in replacements.items():
            # 对 URL 中的变量进行编码，对 Body 和 Headers 则不需要
            url = url.replace(placeholder, urllib.parse.quote_plus(str(value)))
            body = body.replace(placeholder, str(value).replace("\n", "\\n")) # JSON字符串中换行符需要转义
            headers_str = headers_str.replace(placeholder, str(value))

        if "$image" in body:
            image_base64 = ""
            if image:
                image.seek(0)
                image_base64 = base64.b64encode(image.getvalue()).decode('utf-8')
            body = body.replace("$image", image_base64)

        # 解析 headers 字符串为字典
        try:
            headers = json.loads(headers_str) if headers_str and headers_str != "{}" else {}
        except json.JSONDecodeError:
            # 如果解析失败，尝试解析为键值对格式
            headers = {}
            if headers_str and headers_str != "{}":
                for line in headers_str.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        headers[key.strip()] = value.strip()

        # 添加 Content-Type
        headers['Content-Type'] = content_type

        self.log_info(f"发送 Webhook 请求: {method} {url}")
        self.log_info(f"请求头: {headers}")
        self.log_info(f"请求体: {body}")

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=body.encode("utf-8"),
            timeout=15
        )

        # 通过 response.raise_for_status() 可以自动检查 4xx/5xx 错误并抛出异常
        response.raise_for_status()

        self.log_info(f"Webhook 推送成功！状态码: {response.status_code}")

    def add_notify_function(self) -> list:
        notify_function = []
        if self.get_config("BARK_PUSH"):
            notify_function.append(self.bark)
        if self.get_config("CONSOLE"):
            notify_function.append(self.console)
        if self.get_config("DD_BOT_TOKEN") and self.get_config("DD_BOT_SECRET"):
            notify_function.append(self.dingding_bot)
        if self.get_config("FS_KEY"):
            notify_function.append(self.feishu_bot)
        if self.get_config("ONEBOT_URL"):
            notify_function.append(self.one_bot)
        if self.get_config("GOTIFY_URL") and self.get_config("GOTIFY_TOKEN"):
            notify_function.append(self.gotify)
        if self.get_config("IGOT_PUSH_KEY"):
            notify_function.append(self.iGot)
        if self.get_config("SERVERCHAN_PUSH_KEY"):
            notify_function.append(self.serverchan)
        if self.get_config("DEER_KEY"):
            notify_function.append(self.pushdeer)
        if self.get_config("CHAT_URL") and self.get_config("CHAT_TOKEN"):
            notify_function.append(self.chat)
        if self.get_config("PUSH_PLUS_TOKEN"):
            notify_function.append(self.pushplus_bot)
        if self.get_config("WE_PLUS_BOT_TOKEN"):
            notify_function.append(self.weplus_bot)
        if self.get_config("QMSG_KEY") and self.get_config("QMSG_TYPE"):
            notify_function.append(self.qmsg_bot)
        if self.get_config("QYWX_AM"):
            notify_function.append(self.wecom_app)
        if self.get_config("QYWX_KEY"):
            notify_function.append(self.wecom_bot)
        if self.get_config("DISCORD_BOT_TOKEN") and self.get_config("DISCORD_USER_ID"):
            notify_function.append(self.discord_bot)
        if self.get_config("TG_BOT_TOKEN") and self.get_config("TG_USER_ID"):
            notify_function.append(self.telegram_bot)
        if (
            self.get_config("AIBOTK_KEY")
            and self.get_config("AIBOTK_TYPE")
            and self.get_config("AIBOTK_NAME")
        ):
            notify_function.append(self.aibotk)
        if (
            self.get_config("SMTP_SERVER")
            and self.get_config("SMTP_EMAIL")
            and self.get_config("SMTP_PASSWORD")
            and self.get_config("SMTP_NAME")
        ):
            notify_function.append(self.smtp)
        if self.get_config("PUSHME_KEY"):
            notify_function.append(self.pushme)
        if (
            self.get_config("CHRONOCAT_URL")
            and self.get_config("CHRONOCAT_QQ")
            and self.get_config("CHRONOCAT_TOKEN")
        ):
            notify_function.append(self.chronocat)
        if self.get_config("WEBHOOK_URL") and self.get_config("WEBHOOK_BODY"):
            notify_function.append(self.webhook_bot)
        if self.get_config("NTFY_TOPIC"):
            notify_function.append(self.ntfy)
        if self.get_config("WXPUSHER_APP_TOKEN") and (
            self.get_config("WXPUSHER_TOPIC_IDS") or self.get_config("WXPUSHER_UIDS")
        ):
            notify_function.append(self.wxpusher_bot)
        if not notify_function:
            self.log_error(f"无推送渠道，请检查通知设置是否正确")
        return notify_function


    def log_info(self, message: str) -> None:
        """记录信息日志"""
        log.info(f'指令[ 通知 ] {message}')


    def log_error(self, message: str) -> None:
        """记录错误日志"""
        log.error(f'指令[ 通知 ] {message}')


    def get_config(self, key: str, default: str = '') -> str:
        """获取推送配置值"""
        value = getattr(self.ctx.push_config, key.lower(), default)
        if value:
            return str(value).strip()
        return default


    def send(self, content: str, image: Optional[BytesIO] = None, test_method: Optional[str] = None) -> None:
        title = self.ctx.push_config.custom_push_title

        if test_method:
            # 测试指定的推送方式
            notify_function = self.get_specific_notify_function(test_method)
        else:
            # 使用所有已配置的推送方式
            notify_function = self.add_notify_function()
            if not notify_function:
                raise ValueError("未找到可用的推送方式，请检查通知设置是否正确")

        # 遥测埋点：记录推送方法使用情况
        self._track_push_usage(notify_function, test_method)

        # 如果是测试模式，直接在主线程中执行，这样异常可以被前端捕获
        if test_method:
            for mode in notify_function:
                mode(title, content, image)
        else:
            # 正常推送使用多线程
            ts = [
                threading.Thread(target=mode, args=(title, content, image), name=mode.__name__)
                for mode in notify_function
            ]
            [t.start() for t in ts]
            [t.join() for t in ts]

    def get_specific_notify_function(self, method: str) -> list:
        """获取指定的推送方式函数"""
        # 直接从add_notify_function获取所有可用的通知方式
        all_functions = self.add_notify_function()

        # 通过方法名匹配对应的函数
        method = method.upper()

        # 配置键名到函数名的映射（UI传入的method已经是配置键名）
        method_to_function_name = {
            'BARK': 'bark',
            'CONSOLE': 'console',
            'DD_BOT': 'dingding_bot',
            'FS': 'feishu_bot',
            'ONEBOT': 'one_bot',
            'GOTIFY': 'gotify',
            'IGOT': 'iGot',
            'SERVERCHAN': 'serverchan',
            'DEER': 'pushdeer',
            'CHAT': 'chat',
            'PUSH_PLUS': 'pushplus_bot',
            'WE_PLUS_BOT': 'weplus_bot',
            'QMSG': 'qmsg_bot',
            'QYWX': 'wecom_bot',
            'DISCORD': 'discord_bot',
            'TG': 'telegram_bot',
            'AIBOTK': 'aibotk',
            'SMTP': 'smtp',
            'PUSHME': 'pushme',
            'CHRONOCAT': 'chronocat',
            'WEBHOOK': 'webhook_bot',
            'NTFY': 'ntfy',
            'WXPUSHER': 'wxpusher_bot',
        }

        target_function_name = method_to_function_name.get(method)
        if not target_function_name:
            raise ValueError(f"未支持的推送方式: {method}")

        # 查找匹配的函数
        for func in all_functions:
            if func.__name__ == target_function_name:
                return [func]

        raise ValueError(f"{method} 推送方式未正确配置")

    def _track_push_usage(self, notify_functions: list, test_method: Optional[str] = None) -> None:
        """跟踪推送方法使用情况"""
        if hasattr(self.ctx, 'telemetry') and self.ctx.telemetry:
            # 获取启用的推送方法
            enabled_methods = [func.__name__ for func in notify_functions]

            # 记录推送方法使用情况
            self.ctx.telemetry.track_feature_usage('push_methods', {
                'enabled_methods': enabled_methods,
                'total_methods': len(enabled_methods),
                'is_test': test_method is not None,
                'test_method': test_method,
                'has_image': hasattr(self, '_last_image') and self._last_image is not None
            })

            # 记录每种推送方法的使用
            for method_name in enabled_methods:
                self.ctx.telemetry.track_feature_usage(f'push_method_{method_name}', {
                    'method_name': method_name,
                    'is_test': test_method is not None
                })

    def _track_push_success(self, method_name: str) -> None:
        """跟踪推送成功"""
        if hasattr(self.ctx, 'telemetry') and self.ctx.telemetry:
            self.ctx.telemetry.track_feature_usage(f'push_success_{method_name}', {
                'method_name': method_name,
                'status': 'success'
            })

    def _track_push_failure(self, method_name: str, error_message: str) -> None:
        """跟踪推送失败"""
        if hasattr(self.ctx, 'telemetry') and self.ctx.telemetry:
            self.ctx.telemetry.track_feature_usage(f'push_failure_{method_name}', {
                'method_name': method_name,
                'status': 'failure',
                'error_message': error_message
            })

    def _compress_image(self, image: BytesIO, target_size: int) -> tuple[bytes | None, str | None, int]:
        """
        自动将图片压缩为渐进式 JPG,使用二分搜索质量,尽量贴近 2MB 上限
        """
        import cv2
        import numpy as np

        image.seek(0)
        data = image.getvalue()
        if not data:
            return None, None, -1

        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None, None, -1

        # JPEG 仅支持 1/3 通道，若为 4 通道则转为 BGR
        if len(img.shape) == 2:
            bgr = img
        else:
            if img.shape[2] == 4:
                bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            elif img.shape[2] == 3:
                bgr = img
            else:
                bgr = img[:, :, :3]

        best: bytes | None = None
        best_q: int = -1

        # 二分搜索质量，尽量贴近 2MB
        lo, hi = 30, 90
        while lo <= hi:
            q = (lo + hi) // 2
            params = [
                int(cv2.IMWRITE_JPEG_QUALITY), int(q),
                int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,
                int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1,
            ]
            ok, enc = cv2.imencode('.jpg', bgr, params)
            if not ok:
                break
            size = enc.nbytes
            if size <= target_size:
                best = enc.tobytes()
                best_q = q
                lo = q + 1  # 尝试更高质量
            else:
                hi = q - 1  # 降低质量

        if best:
            return best, 'jpeg', best_q
        else:
            return None, None, -1


def main():
    Push.send("content")

if __name__ == "__main__":
    main()
