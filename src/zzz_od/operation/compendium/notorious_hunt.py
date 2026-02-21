import time
from typing import ClassVar

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
)
from zzz_od.application.notorious_hunt import notorious_hunt_const
from zzz_od.application.notorious_hunt.notorious_hunt_config import (
    NotoriousHuntConfig,
    NotoriousHuntLevelEnum,
)
from zzz_od.application.notorious_hunt.notorious_hunt_run_record import (
    NotoriousHuntRunRecord,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.challenge_mission.check_next_after_battle import (
    ChooseNextOrFinishAfterBattle,
)
from zzz_od.operation.challenge_mission.exit_in_battle import ExitInBattle
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam
from zzz_od.operation.compendium.notorious_hunt_move import NotoriousHuntMove
from zzz_od.operation.restore_charge import RestoreCharge
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum


class NotoriousHunt(ZOperation):

    STATUS_WITH_LEFT_TIMES: ClassVar[str] = '有剩余次数'
    STATUS_NO_LEFT_TIMES: ClassVar[str] = '没有剩余次数'
    STATUS_CHARGE_NOT_ENOUGH: ClassVar[str] = '电量不足'
    STATUS_FIGHT_TIMEOUT: ClassVar[str] = '战斗超时'

    def __init__(self, ctx: ZContext, plan: ChargePlanItem,
                 use_charge_power: bool = False):
        """
        使用快捷手册传送后
        用这个进行挑战
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name='%s %s' % (
                gt('恶名狩猎', 'game'),
                gt(plan.mission_type_name, 'game')
            )
        )
        self.charge_plan_config: ChargePlanConfig = self.ctx.run_context.get_config(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.config: NotoriousHuntConfig = self.ctx.run_context.get_config(
            app_id=notorious_hunt_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.run_record: NotoriousHuntRunRecord = self.ctx.run_context.get_run_record(
            app_id=notorious_hunt_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
        )

        self.plan: ChargePlanItem = plan
        self.use_charge_power: bool = use_charge_power  # 是否使用电量 深度追猎
        self.can_run_times: int = -1

    def _match_mission_type(self, target_name: str, ocr_result: str) -> bool:
        """
        匹配任务类型名称（支持别名双向查找）
        """
        names = [target_name]
        hunt_category = self.ctx.compendium_service.get_category_data('训练', '恶名狩猎')
        if hunt_category:
            for mt in hunt_category.mission_type_list:
                if mt.mission_type_name == target_name or target_name in mt.alias_list:
                    names.append(mt.mission_type_name)
                    names.extend(mt.alias_list)
                    names = list(set(names))
                    break
        return any(str_utils.find_by_lcs(gt(n, 'game'), ocr_result, percent=0.5) for n in names)

    @operation_node(name='等待入口加载', node_max_retry_times=60)
    def wait_entry_load(self) -> OperationRoundResult:
        r1 = self.round_by_find_area(self.last_screenshot, '恶名狩猎', '当期剩余奖励次数')
        if r1.is_success:
            return self.round_success(r1.status, wait=1)  # 画面加载有延时 稍微等待

        r2 = self.round_by_find_area(self.last_screenshot, '恶名狩猎', '按钮-街区')
        if r2.is_success:
            return self.round_success(r2.status, wait=1)  # 画面加载有延时 稍微等待

        return self.round_retry(r1.status, wait=1)

    @node_from(from_name='等待入口加载', status='按钮-街区')
    @operation_node(name='判断副本名称')
    def check_mission(self) -> OperationRoundResult:
        if self.plan.mission_type_name == '代理人方案培养':
        # 通过代理人进入则跳过重新选择副本
            return self.round_success()
        area = self.ctx.screen_loader.get_area('恶名狩猎', '标题-副本名称')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        is_target_mission: bool = False  # 当前是否目标副本

        for ocr_result in ocr_result_map.keys():
            if self._match_mission_type(self.plan.mission_type_name, ocr_result):
                is_target_mission = True
                break

        if is_target_mission:
            return self.round_success()
        else:
            return self.round_by_click_area('菜单', '返回', success_wait=1)

    @node_from(from_name='等待入口加载', status='当期剩余奖励次数')  # 最开始在外面的副本列表
    @node_from(from_name='判断副本名称', status='返回')  # 当前副本不符合 返回列表重新选择
    @operation_node(name='选择副本')
    def choose_mission(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('恶名狩猎', '副本名称列表')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)

        ocr_result_map = self.ctx.ocr.run_ocr(part)

        for ocr_result, mrl in ocr_result_map.items():
            if self._match_mission_type(self.plan.mission_type_name, ocr_result):
                to_click = mrl.max.center + area.left_top + Point(0, 100)
                if self.ctx.controller.click(to_click):
                    return self.round_success(wait=2)

        # 未匹配时 判断该往哪边滑动
        hunt_category = self.ctx.compendium_service.get_category_data('训练', '恶名狩猎')
        with_left: bool = False  # 当前识别有在目标左边的副本
        for mission_type in reversed(hunt_category.mission_type_list):
            if self._match_mission_type(self.plan.mission_type_name, mission_type.mission_type_name):
                break

            find: bool = False  # 当前画面有没有识别到 mission_type
            for ocr_result, mrl in ocr_result_map.items():
                if str_utils.find_by_lcs(gt(mission_type.mission_type_name, 'game'), ocr_result, percent=0.5):
                    find = True
                    break

            if find:
                with_left = True

        drag_from = area.center
        if with_left:
            drag_to = Point(drag_from.x - 500, drag_from.y)
        else:
            drag_to = Point(drag_from.x + 500, drag_from.y)
        self.ctx.controller.drag_to(start=drag_from, end=drag_to)

        return self.round_retry(f'未能识别{self.plan.mission_type_name}', wait_round_time=2)

    @node_from(from_name='判断副本名称')  # 当前副本符合 继续选择
    @node_from(from_name='选择副本')
    @operation_node(name='选择深度追猎')
    def choose_by_use_power(self):
        result = self.round_by_find_area(self.last_screenshot, '恶名狩猎', '按钮-深度追猎-ON')
        current_use_power = result.is_success  # 当前在深度追猎模式

        if self.use_charge_power == current_use_power:
            return self.round_success()

        # 选择深度追猎之后的对话框
        result = self.round_by_find_and_click_area(self.last_screenshot, '恶名狩猎', '按钮-深度追猎-确认')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        self.round_by_click_area('恶名狩猎', '按钮-深度追猎-ON')
        return self.round_retry(wait=1)

    @node_from(from_name='选择深度追猎')
    @operation_node(name='识别可运行次数')
    def check_can_run_times(self) -> OperationRoundResult:
        if self.use_charge_power:  # 深度追猎
            return self.round_success(NotoriousHunt.STATUS_WITH_LEFT_TIMES)
        else:
            result = self.round_by_find_area(self.last_screenshot, '恶名狩猎', '按钮-无报酬模式')
            if result.is_success:  # 可能是其他设备挑战了 没有剩余次数了
                self.run_record.left_times = 0
                return self.round_success(NotoriousHunt.STATUS_NO_LEFT_TIMES)

            area = self.ctx.screen_loader.get_area('恶名狩猎', '剩余次数')
            part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)

            ocr_result = self.ctx.ocr.run_ocr_single_line(part)
            left_times = str_utils.get_positive_digits(ocr_result, None)
            if left_times is None:  # 识别不到时 使用记录中的数量
                self.can_run_times = self.run_record.left_times
            else:
                self.can_run_times = left_times

            # 运行次数上限是计划剩余次数
            need_run_times = self.plan.plan_times - self.plan.run_times
            if self.can_run_times > need_run_times:
                self.can_run_times = need_run_times

            return self.round_success(NotoriousHunt.STATUS_WITH_LEFT_TIMES)

    @node_from(from_name='识别可运行次数', status=STATUS_WITH_LEFT_TIMES)
    @operation_node(name='选择难度')
    def choose_level(self) -> OperationRoundResult:
        if self.plan.level == NotoriousHuntLevelEnum.DEFAULT.value.value:
            return self.round_success()

        self.round_by_click_area('恶名狩猎', '难度选择入口')
        time.sleep(1)

        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('恶名狩猎', '难度选择区域')
        result = self.round_by_ocr_and_click(screen, self.plan.level, area=area,
                                           success_wait=1)

        # 如果选择的是最高难度 那第一下有可能选中不到 多选一下兜底
        screen = self.screenshot()
        self.round_by_ocr_and_click(screen, self.plan.level, area=area,
                                    success_wait=1)

        if result.is_success:
            return result
        else:
            return self.round_retry(result.status, wait=1)

    @node_from(from_name='选择难度')
    @node_from(from_name='恢复电量', status='恢复电量成功')
    @operation_node(name='下一步', node_max_retry_times=10)  # 部分机器加载较慢 延长出战的识别时间
    def click_next(self) -> OperationRoundResult:
        # 防止前面电量识别错误
        result = self.round_by_find_area(self.last_screenshot, '恢复电量', '标题')
        if result.is_success:
            return self.round_success(status=NotoriousHunt.STATUS_CHARGE_NOT_ENOUGH)

        # 点击直到出战按钮出现
        result = self.round_by_find_area(self.last_screenshot, '实战模拟室', '出战')
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_and_click_area(self.last_screenshot, '实战模拟室', '下一步')
        if result.is_success:
            time.sleep(0.5)
            self.ctx.controller.mouse_move(ScreenNormalWorldEnum.UID.value.center)  # 点击后 移开鼠标 防止识别不到出战
            return self.round_wait(result.status, wait=0.5)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='下一步', status=STATUS_CHARGE_NOT_ENOUGH)
    @operation_node(name='恢复电量')
    def restore_charge(self) -> OperationRoundResult:
        if not self.charge_plan_config.is_restore_charge_enabled:
            return self.round_success(NotoriousHunt.STATUS_CHARGE_NOT_ENOUGH)
        op = RestoreCharge(self.ctx)
        result = self.round_by_op_result(op.execute())
        return result if result.is_success else self.round_success(NotoriousHunt.STATUS_CHARGE_NOT_ENOUGH)

    @node_from(from_name='下一步', status='出战')
    @operation_node(name='选择预备编队')
    def choose_predefined_team(self) -> OperationRoundResult:
        if self.plan.predefined_team_idx == -1:
            return self.round_success('无需选择预备编队')
        else:
            op = ChoosePredefinedTeam(self.ctx, [self.plan.predefined_team_idx])
            return self.round_by_op_result(op.execute())

    @node_from(from_name='选择预备编队')
    @operation_node(name='出战')
    def click_start(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot, '实战模拟室', '出战',
            success_wait=1, retry_wait_round=1
        )

    @node_from(from_name='出战')
    @node_from(from_name='重新开始-确认')
    @operation_node(name='加载自动战斗指令')
    def init_auto_battle(self) -> OperationRoundResult:
        if self.plan.predefined_team_idx == -1:
            auto_battle = self.plan.auto_battle_config
        else:
            team_list = self.ctx.team_config.team_list
            auto_battle = team_list[self.plan.predefined_team_idx].auto_battle

        self.ctx.auto_battle_context.init_auto_op(
            sub_dir='auto_battle',
            op_name=auto_battle,
        )
        return self.round_success()

    @node_from(from_name='加载自动战斗指令')
    @operation_node(name='等待战斗画面加载', node_max_retry_times=60, is_start_node=False)
    def wait_battle_screen(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击')
        if result.is_success:
            return self.round_success(self.plan.mission_type_name)

        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
        if result.is_success:
            return self.round_success(self.plan.mission_type_name)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='战斗前移动')
    def run_battle(self) -> OperationRoundResult:
        op = NotoriousHuntMove(self.ctx, self.plan.notorious_hunt_buff_num)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='战斗前移动')
    @node_from(from_name='战斗失败', status='战斗结果-倒带')
    @operation_node(name='开始自动战斗')
    def start_auto_op(self) -> OperationRoundResult:
        self.ctx.auto_battle_context.start_auto_battle()
        return self.round_success()

    @node_from(from_name='开始自动战斗')
    @operation_node(name='自动战斗', mute=True, timeout_seconds=600)
    def auto_battle(self) -> OperationRoundResult:
        if self.ctx.auto_battle_context.last_check_end_result is not None:
            self.ctx.auto_battle_context.stop_auto_battle()
            return self.round_success(status=self.ctx.auto_battle_context.last_check_end_result)

        self.ctx.auto_battle_context.check_battle_state(
            self.last_screenshot, self.last_screenshot_time,
            check_battle_end_normal_result=True,
        )

        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='自动战斗', status='普通战斗-撤退')
    @operation_node(name='战斗失败')
    def battle_fail(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(self.last_screenshot, '战斗画面', '战斗结果-倒带')

        if result.is_success:
            self.ctx.auto_battle_context.last_check_end_result = None
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(self.last_screenshot, '战斗画面', '战斗结果-撤退')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='战斗失败', status='战斗结果-撤退')
    @operation_node(name='战斗失败退出')
    def battle_fail_exit(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(self.last_screenshot, '战斗画面', '战斗结果-退出')

        if result.is_success:  # 战斗失败 返回失败到外层 中断后续挑战
            return self.round_fail(result.status, wait=10)
        else:
            return self.round_retry(result.status, wait=1)

    @node_from(from_name='战斗前移动', success=False)
    @node_from(from_name='自动战斗', success=False, status=Operation.STATUS_TIMEOUT)
    @operation_node(name='退出战斗')
    def exit_battle(self) -> OperationRoundResult:
        self.ctx.auto_battle_context.stop_auto_battle()
        op = ExitInBattle(self.ctx, '战斗-挑战结果-失败', '按钮-退出')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='退出战斗')
    @operation_node(name='点击挑战结果退出')
    def click_result_exit(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(screen_name='战斗-挑战结果-失败', area_name='按钮-退出',
                                                   until_not_find_all=[('战斗-挑战结果-失败', '按钮-退出')],
                                                   success_wait=1, retry_wait=1)
        if result.is_success:
            return self.round_fail(status=NotoriousHunt.STATUS_FIGHT_TIMEOUT)
        else:
            return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='自动战斗')
    @node_notify(when=NotifyTiming.CURRENT_SUCCESS, detail=True)
    @operation_node(name='战斗结束')
    def after_battle(self) -> OperationRoundResult:
        self.can_run_times -= 1
        if self.use_charge_power:
            self.charge_plan_config.add_plan_run_times(self.plan)
        else:
            self.run_record.left_times = self.run_record.left_times - 1
            self.config.add_plan_run_times(self.plan)
        return self.round_success()

    @node_from(from_name='战斗结束')
    @operation_node(name='判断下一次')
    def check_next(self) -> OperationRoundResult:
        if self.use_charge_power:
            try_next = self.plan.plan_times > self.plan.run_times
        else:
            try_next = self.can_run_times > 0
        op = ChooseNextOrFinishAfterBattle(self.ctx, try_next)
        result = op.execute()
        if result.status == '战斗结果-完成' and self.can_run_times > 0:
            # 可能是其他设备挑战了 没有剩余次数了
            self.run_record.left_times = 0
        return self.round_by_op_result(result)

    @node_from(from_name='判断下一次', status='战斗结果-再来一次')
    @operation_node(name='重新开始-确认')
    def restart_confirm(self) -> OperationRoundResult:
        if self.use_charge_power:  # 使用体力的时候不需要重新确认
            return self.round_success()
        return self.round_by_find_and_click_area(self.last_screenshot, '恶名狩猎', '重新开始-确认',
                                                 success_wait=1, retry_wait_round=1)

    @node_from(from_name='判断下一次', status='战斗结果-完成')
    @operation_node(name='等待返回入口', node_max_retry_times=60)
    def wait_back_to_entry(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '恶名狩猎', '剩余奖励次数')
        if result.is_success:  # 普通模式
            return self.round_success(wait=1)

        result = self.round_by_find_area(self.last_screenshot, '恶名狩猎', '按钮-街区')
        if result.is_success:  # 深度追猎
            return self.round_success(wait=1)

        return self.round_retry(result.status, wait=1)

    def handle_pause(self, e=None):
        self.ctx.auto_battle_context.stop_auto_battle()

    def handle_resume(self, e=None):
        if self.current_node.node is not None and self.current_node.node.cn == '自动战斗':
            self.ctx.auto_battle_context.resume_auto_battle()


def __debug_charge():
    """
    测试电量识别
    @return:
    """
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('_1742622386361')
    area = ctx.screen_loader.get_area('恶名狩猎', '文本-剩余电量')
    part = cv2_utils.crop_image_only(screen, area.rect)
    ocr_result = ctx.ocr.run_ocr_single_line(part)
    print(ocr_result)


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    op = NotoriousHunt(
        ctx,
        ChargePlanItem(
            category_name='恶名狩猎',
            mission_type_name='初生死路屠夫',
            level=NotoriousHuntLevelEnum.DEFAULT.value.value,
            auto_battle_config='全配对通用',
            predefined_team_idx=0,
        ),
        use_charge_power=False)
    op.can_run_times = 1
    op.auto_op = None
    op.init_auto_battle()

    op.execute()


if __name__ == '__main__':
    __debug()
