from typing import Any

from PySide6.QtCore import QTimer

from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class AdapterInitMixin:
    """为依赖 ``YamlConfigAdapter`` 的控件提供统一的初始化逻辑。"""

    adapter: YamlConfigAdapter | None
    _adapter_load_generation: int

    def __init__(self, *args, **kwargs) -> None:
        # Qt 的 C++ 基类经常使用非协作式初始化，这里不调用 super().__init__，
        # 以避免 "object.__init__() takes exactly one argument" 的错误。
        # 仍保留 *args/**kwargs 形参，确保与各调用端签名兼容。
        self.adapter = None
        self._adapter_load_generation = 0

    def init_with_adapter(self, adapter: YamlConfigAdapter | None) -> None:
        """绑定适配器并异步同步初始值。"""
        self.adapter = adapter
        self._adapter_load_generation += 1
        current_generation = self._adapter_load_generation

        if adapter is None:
            self._schedule_value_apply(self.default_adapter_value(), current_generation)
            return

        def load_value():
            try:
                value = self._get_adapter_value(adapter)
                self._schedule_value_apply(value, current_generation)
            except Exception:
                log.error("加载配置项失败", exc_info=True)

        QTimer.singleShot(0, load_value)

    def default_adapter_value(self) -> Any:
        """当没有适配器时使用的默认值。"""
        return None

    def _get_adapter_value(self, adapter: YamlConfigAdapter) -> Any:
        return adapter.get_value()

    def _apply_adapter_value(self, value: Any) -> None:
        self._set_value_from_adapter(value)
        self._on_adapter_value_applied(value)

    def _set_value_from_adapter(self, value: Any) -> None:
        set_value = getattr(self, "setValue", None)
        if callable(set_value):
            set_value(value, emit_signal=False)
            return

        raise NotImplementedError(
            "使用 AdapterInitMixin 的类必须实现 setValue 方法，或重写 _set_value_from_adapter 方法。"
        )

    def _on_adapter_value_applied(self, value: Any) -> None:
        """值被应用后调用，可用于执行额外逻辑。"""
        pass

    def _schedule_value_apply(self, value: Any, generation: int) -> None:
        def apply_value():
            if generation != self._adapter_load_generation:
                return
            self._apply_adapter_value(value)

        QTimer.singleShot(0, apply_value)
