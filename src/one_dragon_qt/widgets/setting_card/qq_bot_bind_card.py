import contextlib
import threading
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import FluentIcon, InfoBar, PushButton

from one_dragon.base.push.channel.qq_bot import (
    bind_group_openid,
    bind_user_openid,
)
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)


class QQBotBindRunner(QThread):
    """后台跑 QQ 机器人绑定，等验证码期间不阻塞界面"""

    status_signal = Signal(str)
    verify_signal = Signal(str)  # 验证码文案，卡片另外弹一条常驻提示
    result_signal = Signal(bool, str, str)  # 是否群聊、openid、错误信息

    def __init__(
        self,
        app_id: str,
        client_secret: str,
        is_group: bool,
        parent: QWidget | None = None,
    ) -> None:
        """
        初始化绑定任务

        Args:
            app_id: 机器人 AppID
            client_secret: 机器人 AppSecret
            is_group: 绑定群聊还是单聊
            parent: 父组件
        """
        QThread.__init__(self, parent)
        self._app_id: str = app_id
        self._client_secret: str = client_secret
        self._is_group: bool = is_group
        self._cancel_event: threading.Event = threading.Event()

    def cancel(self) -> None:
        """用户点取消时置位，绑定流程会在下一次收消息超时时退出"""
        self._cancel_event.set()

    def run(self) -> None:
        """跑绑定流程，结果通过 result_signal 发回界面线程"""
        try:
            if self._is_group:
                openid, err = bind_group_openid(
                    self._app_id,
                    self._client_secret,
                    self._on_group_verify_code,
                    self.status_signal.emit,
                    self._cancel_event,
                )
            else:
                openid, err = bind_user_openid(
                    self._app_id,
                    self._client_secret,
                    self._on_user_verify_code,
                    self._cancel_event,
                )
            self.result_signal.emit(self._is_group, openid, err)
        except Exception as e:
            log.error('QQ 官方机器人绑定异常', exc_info=True)
            self.result_signal.emit(self._is_group, '', f'绑定失败：{e}')

    def _on_user_verify_code(self, code: str) -> None:
        """单聊的验证码提示：让用户私聊机器人发出去"""
        msg = f'验证码 {code}，请用手机 QQ 私聊机器人发送'
        self.status_signal.emit(msg)
        self.verify_signal.emit(msg)

    def _on_group_verify_code(self, code: str) -> None:
        """群聊的验证码提示：拉进群或在群里 @机器人 发出去"""
        msg = f'验证码 {code}，请把机器人拉进群或在群里 @机器人 发送'
        self.status_signal.emit(msg)
        self.verify_signal.emit(msg)


class QQBotBindCard(MultiPushSettingCard):
    """QQ 官方机器人接收方绑定卡片

    单聊和群聊的 openid 只能从机器人网关收到的事件里取，卡片提供两个绑定按钮，
    绑定跑在后台线程，成功后通过 openid_bound 把结果交给界面写入配置。
    """

    openid_bound = Signal(bool, str)  # 是否群聊、openid
    bind_failed = Signal(str)  # 错误信息

    def __init__(
        self,
        get_app_credentials: Callable[[], tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        """
        初始化绑定卡片

        Args:
            get_app_credentials: 取当前 AppID 与 AppSecret 的回调，点绑定时才读最新值
            parent: 父组件
        """
        self._get_app_credentials: Callable[[], tuple[str, str]] = get_app_credentials
        self._runner: QQBotBindRunner | None = None
        self._verify_bar: InfoBar | None = None

        self.bind_user_btn = PushButton(text='绑定单聊', icon=FluentIcon.PEOPLE)
        self.bind_user_btn.clicked.connect(lambda: self._start_bind(False))
        self.bind_group_btn = PushButton(text='绑定群聊', icon=FluentIcon.PEOPLE)
        self.bind_group_btn.clicked.connect(lambda: self._start_bind(True))
        self.cancel_btn = PushButton(text='取消', icon=FluentIcon.CANCEL)
        self.cancel_btn.clicked.connect(self._cancel_bind)
        self.cancel_btn.setVisible(False)

        MultiPushSettingCard.__init__(
            self,
            icon=FluentIcon.SYNC,
            title="自动获取接收方 <span style='color: #ff6b6b;'>*</span>",
            content='点绑定后按提示用 QQ 给机器人发验证码，OpenID 自动填入下方',
            btn_list=[self.bind_user_btn, self.bind_group_btn, self.cancel_btn],
            parent=parent,
        )

        # 绑定最长要等 60 秒，退出时先取消再等线程收尾，否则线程还在跑就被父对象析构，Qt 会直接终止进程
        QApplication.instance().aboutToQuit.connect(self._stop_runner)

    def _start_bind(self, is_group: bool) -> None:
        """
        开始绑定接收方

        Args:
            is_group: 绑定群聊还是单聊
        """
        if self._runner is not None:
            return

        app_id, client_secret = self._get_app_credentials()
        if len(app_id) == 0 or len(client_secret) == 0:
            self.bind_failed.emit('请先填写 AppID 与 AppSecret，再点绑定')
            return

        self._runner = QQBotBindRunner(app_id, client_secret, is_group, self)
        self._runner.status_signal.connect(self.setContent)
        self._runner.verify_signal.connect(self._show_verify_code)
        self._runner.result_signal.connect(self._on_bind_result)
        self._runner.finished.connect(self._on_bind_finished)
        self._set_binding(True)
        self.setContent('正在连接 QQ 网关…')
        self._runner.start()

    def _cancel_bind(self) -> None:
        """取消绑定，断开网关连接"""
        if self._runner is not None:
            self._runner.cancel()

    def _stop_runner(self) -> None:
        """程序退出前停掉绑定线程，避免线程还在跑就被父对象析构"""
        runner = self._runner
        if runner is None:
            return

        # 退出路径上不需要再弹“已取消绑定”的提示
        runner.result_signal.disconnect(self._on_bind_result)
        runner.cancel()
        if not runner.wait(3000):
            log.warning('QQ 机器人绑定线程未在退出前结束')

    def _show_verify_code(self, msg: str) -> None:
        """验证码另弹一条不自动消失的提示，卡片里那行灰色小字容易被忽略"""
        self._close_verify_bar()
        self._verify_bar = InfoBar.warning(
            title='绑定 QQ 机器人',
            content=msg,
            isClosable=True,
            duration=-1,
            parent=self.window(),
        )

    def _on_bind_result(self, is_group: bool, openid: str, error: str) -> None:
        """绑定结束，成功则把 openid 交给界面写进配置"""
        if len(error) > 0:
            self.setContent(error)
            self.bind_failed.emit(error)
            return

        target = '群聊' if is_group else '单聊'
        self.setContent(f'绑定成功，已自动填入{target} OpenID')
        self.openid_bound.emit(is_group, openid)

    def _on_bind_finished(self) -> None:
        """绑定结束，收起验证码提示并复位按钮"""
        self._close_verify_bar()
        runner = self._runner
        self._runner = None
        self._set_binding(False)
        if runner is not None:
            runner.deleteLater()

    def _set_binding(self, binding: bool) -> None:
        """绑定期间禁用绑定按钮，只留取消"""
        self.cancel_btn.setVisible(binding)
        self.bind_user_btn.setEnabled(not binding)
        self.bind_group_btn.setEnabled(not binding)
        # 禁用按钮会让焦点落到第一个输入框并被全选，这里把焦点留在按钮上
        if binding:
            self.cancel_btn.setFocus()
        else:
            self.bind_user_btn.setFocus()

    def _close_verify_bar(self) -> None:
        """关闭常驻的验证码提示，用户已手动点掉时底层对象可能已被删除"""
        if self._verify_bar is None:
            return

        with contextlib.suppress(RuntimeError):
            self._verify_bar.close()
        self._verify_bar = None
