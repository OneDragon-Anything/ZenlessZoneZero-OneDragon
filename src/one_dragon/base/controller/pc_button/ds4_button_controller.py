from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.controller.pc_button.virtual_gamepad_controller import (
    VirtualGamepadController,
)


class Ds4ButtonEnum(Enum):

    CROSS = ConfigItem('✕', 'ds4_cross')
    CIRCLE = ConfigItem('○', 'ds4_circle')
    SQUARE = ConfigItem('□', 'ds4_square')
    TRIANGLE = ConfigItem('△', 'ds4_triangle')
    L2 = ConfigItem('L2', 'ds4_l2')
    R2 = ConfigItem('R2', 'ds4_r2')
    L1 = ConfigItem('L1', 'ds4_l1')
    R1 = ConfigItem('R1', 'ds4_r1')
    L_STICK_W = ConfigItem('左摇杆-上', 'ds4_ls_up')
    L_STICK_S = ConfigItem('左摇杆-下', 'ds4_ls_down')
    L_STICK_A = ConfigItem('左摇杆-左', 'ds4_ls_left')
    L_STICK_D = ConfigItem('左摇杆-右', 'ds4_ls_right')
    L_THUMB = ConfigItem('左摇杆-按下', 'ds4_l_thumb')
    R_THUMB = ConfigItem('右摇杆-按下', 'ds4_r_thumb')
    DPAD_UP = ConfigItem('十字键-上', 'ds4_dpad_up')
    DPAD_DOWN = ConfigItem('十字键-下', 'ds4_dpad_down')
    DPAD_LEFT = ConfigItem('十字键-左', 'ds4_dpad_left')
    DPAD_RIGHT = ConfigItem('十字键-右', 'ds4_dpad_right')
    OPTIONS = ConfigItem('OPTIONS', 'ds4_options')
    SHARE = ConfigItem('SHARE', 'ds4_share')
    TOUCHPAD = ConfigItem('触控板', 'ds4_touchpad')
    R_STICK_W = ConfigItem('右摇杆-上', 'ds4_rs_up')
    R_STICK_S = ConfigItem('右摇杆-下', 'ds4_rs_down')
    R_STICK_A = ConfigItem('右摇杆-左', 'ds4_rs_left')
    R_STICK_D = ConfigItem('右摇杆-右', 'ds4_rs_right')
    PS = ConfigItem('PS', 'ds4_ps')


class Ds4ButtonController(VirtualGamepadController):

    def __init__(self) -> None:
        VirtualGamepadController.__init__(self)
        if not pc_button_utils.is_vgamepad_installed():
            return

        import vgamepad as vg
        self.pad = vg.VDS4Gamepad()
        btn = vg.DS4_BUTTONS
        dpad = vg.DS4_DPAD_DIRECTIONS
        special = vg.DS4_SPECIAL_BUTTONS

        # 普通按钮
        for key, const in [
            ('ds4_cross', btn.DS4_BUTTON_CROSS),
            ('ds4_circle', btn.DS4_BUTTON_CIRCLE),
            ('ds4_square', btn.DS4_BUTTON_SQUARE),
            ('ds4_triangle', btn.DS4_BUTTON_TRIANGLE),
            ('ds4_l1', btn.DS4_BUTTON_SHOULDER_LEFT),
            ('ds4_r1', btn.DS4_BUTTON_SHOULDER_RIGHT),
            ('ds4_l_thumb', btn.DS4_BUTTON_THUMB_LEFT),
            ('ds4_r_thumb', btn.DS4_BUTTON_THUMB_RIGHT),
            ('ds4_options', btn.DS4_BUTTON_OPTIONS),
            ('ds4_share', btn.DS4_BUTTON_SHARE),
        ]:
            self._register_button(key, const)

        # 扳机
        self._register_trigger('ds4_l2', left=True)
        self._register_trigger('ds4_r2', left=False)

        # DPAD（DS4 需用 directional_pad API）
        none_dir = dpad.DS4_BUTTON_DPAD_NONE
        for key, direction in [
            ('ds4_dpad_up', dpad.DS4_BUTTON_DPAD_NORTH),
            ('ds4_dpad_down', dpad.DS4_BUTTON_DPAD_SOUTH),
            ('ds4_dpad_left', dpad.DS4_BUTTON_DPAD_WEST),
            ('ds4_dpad_right', dpad.DS4_BUTTON_DPAD_EAST),
        ]:
            self._key_bindings[key] = (
                lambda d=direction: self.pad.directional_pad(direction=d),
                lambda n=none_dir: self.pad.directional_pad(direction=n),
            )

        # 特殊按钮 (PS / 触控板)
        for key, sb in [
            ('ds4_ps', special.DS4_SPECIAL_BUTTON_PS),
            ('ds4_touchpad', special.DS4_SPECIAL_BUTTON_TOUCHPAD),
        ]:
            self._key_bindings[key] = (
                lambda s=sb: self.pad.press_special_button(special_button=s),
                lambda s=sb: self.pad.release_special_button(special_button=s),
            )

        # 左摇杆
        for key, x, y in [
            ('ds4_ls_up', 0, 1), ('ds4_ls_down', 0, -1),
            ('ds4_ls_left', -1, 0), ('ds4_ls_right', 1, 0),
        ]:
            self._register_stick(key, stick='left', x=x, y=y)

        # 右摇杆
        for key, x, y in [
            ('ds4_rs_up', 0, 1), ('ds4_rs_down', 0, -1),
            ('ds4_rs_left', -1, 0), ('ds4_rs_right', 1, 0),
        ]:
            self._register_stick(key, stick='right', x=x, y=y)
