import winreg

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext


class DisableAutoHDR(Operation):
    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        Operation.__init__(self, ctx, op_name=gt('禁用HDR'),
                          need_check_game_win=False)

    @operation_node(name='禁用自动HDR', is_start_node=True)
    def disable_auto_hdr(self) -> OperationRoundResult:
        """
        禁用自动HDR，并保存原始设置
        :return: OperationRoundResult
        """
        if self.ctx.game_account_config.game_path == '':
            return self.round_fail('未配置游戏路径')

        try:
            key_path = "Software\\Microsoft\\DirectX\\UserGpuPreferences"
            game_path = self.ctx.game_account_config.game_path

            # 先读取并保存原始值
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                    value, _ = winreg.QueryValueEx(key, game_path)
                    self.ctx.game_config.original_hdr_value = value
                    log.info('已保存原始HDR设置: %s', value)
            except WindowsError:
                self.ctx.game_config.original_hdr_value = None
                log.info('没有找到原始HDR设置')

            # 设置新值禁用HDR
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, game_path, 0, winreg.REG_SZ, "AutoHDREnable=2096;")
                log.info('已设置注册表键值: %s -> AutoHDREnable=2096', game_path)

            return self.round_success('已禁用HDR', wait=0.5)
        except WindowsError as e:
            log.error('设置注册表失败: %s', str(e))
            return self.round_fail('设置注册表失败')

class EnableAutoHDR(Operation):
    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        Operation.__init__(self, ctx, op_name=gt('恢复HDR'),
                          need_check_game_win=True)

    @operation_node(name='启用自动HDR', is_start_node=True)
    def enable_auto_hdr(self) -> OperationRoundResult:
        """
        启用自动HDR，恢复原始设置
        :return: OperationRoundResult
        """
        if self.ctx.game_account_config.game_path == '':
            return self.round_fail('未配置游戏路径')

        try:
            key_path = "Software\\Microsoft\\DirectX\\UserGpuPreferences"
            game_path = self.ctx.game_account_config.game_path

            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                if self.ctx.game_config.original_hdr_value:
                    # 如果有保存的原始值，则恢复
                    winreg.SetValueEx(key, game_path, 0, winreg.REG_SZ, self.ctx.game_config.original_hdr_value)
                    log.info('已恢复原始HDR设置: %s', self.ctx.game_config.original_hdr_value)
                else:
                    # 如果没有原始值，则删除键值
                    winreg.DeleteValue(key, game_path)
                    log.info('已删除HDR设置键值')

            return self.round_success('已启用HDR', wait=0.5)
        except WindowsError as e:
            log.error('修改注册表失败: %s', str(e))
            return self.round_fail('修改注册表失败')