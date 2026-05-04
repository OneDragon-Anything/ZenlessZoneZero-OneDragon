import contextlib
import time


class PcButtonController:

    def __init__(self) -> None:
        self.key_press_time: float = 0.02
        self.combo_press_time: float = 0.5

    def tap(self, key: str) -> None:
        """
        按键
        """
        pass

    def tap_combo(self, keys: list[str]) -> None:
        """顺序按下组合键：先按修饰键等待轮盘，再按动作键，最后全部释放。

        例如 ['xbox_lb', 'xbox_a']:
        1) 按住 LB（不释放）→ 等待 combo_press_time（轮盘出现）
        2) 按住 A（不释放）→ 等待 key_press_time
        3) 逐个释放
        """
        if not keys:
            return
        pressed: list[str] = []
        try:
            for i, key in enumerate(keys):
                if key is not None:
                    self.press(key, press_time=None)  # 按住不放
                    pressed.append(key)
                    if i < len(keys) - 1:
                        time.sleep(self.combo_press_time)
            time.sleep(self.key_press_time)
        finally:
            for key in reversed(pressed):
                with contextlib.suppress(Exception):
                    self.release(key)

    def press(self, key: str, press_time: float | None = None) -> None:
        """
        :param key: 按键
        :param press_time: 持续按键时间。不传入时 代表不松开
        :return:
        """
        pass

    def reset(self) -> None:
        """
        重置状态
        """
        pass

    def release(self, key: str) -> None:
        """
        施释放按键
        """
        pass

    def set_key_press_time(self, key_press_time: float) -> None:
        self.key_press_time = key_press_time
