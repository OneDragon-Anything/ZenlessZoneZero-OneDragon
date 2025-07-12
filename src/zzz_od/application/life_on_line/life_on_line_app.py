import time

from typing import ClassVar

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.life_on_line.life_on_line_run_record import LifeOnLineRunRecord
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.hdd.enter_hdd_mission import EnterHddMission
from zzz_od.operation.key_sim_runner import KeySimRunner
from zzz_od.operation.transport import Transport
from zzz_od.operation.wait_normal_world import WaitNormalWorld


class LifeOnLineApp(ZApplication):

    STATUS_TIMES_FINISHED: ClassVar[str] = '完成指定次数'
    STATUS_CONTINUE: ClassVar[str] = '继续'
    STATUS_CONTINUE_OVER_NIGHT: ClassVar[str] = '过夜后继续'


    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='life_on_line',
            op_name=gt('真拿命验收'),
            run_record=ctx.life_on_line_record,
            need_notify=True,
        )
        self.run_record: LifeOnLineRunRecord = ctx.life_on_line_record
        self.is_over_night: bool = False  # 本次结束是否过夜了
        self.chosen_team: bool = False  # 是否已经选择过配队了

    @node_from(from_name='检查运行次数', status=STATUS_CONTINUE_OVER_NIGHT)
    @operation_node(name='传送', is_start_node=True)
    def tp(self) -> OperationRoundResult:
        op = Transport(self.ctx, '录像店', 'HDD')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='等待加载')
    def wait_world(self) -> OperationRoundResult:
        op = WaitNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='等待加载')
    @operation_node(name='交互')
    def interact(self) -> OperationRoundResult:
        screen = self.screenshot()
        result = self.round_by_find_area(screen, 'HDD', '街区')
        if result.is_success:
            return self.round_success()

        self.ctx.controller.interact(press=True, press_time=0.2, release=True)
        time.sleep(1)

        return self.round_wait()

    @node_from(from_name='交互')
    @node_from(from_name='检查运行次数', status=STATUS_CONTINUE)
    @operation_node(name='进入副本')
    def enter_mission(self) -> OperationRoundResult:
        target_team_idx: int = self.ctx.life_on_line_config.predefined_team_idx
        if self.chosen_team:  # 只需要选1次
            target_team_idx = -1
        op = EnterHddMission(self.ctx, '第二章间章', '战斗委托', '作战真拿命验收',
                             target_team_idx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='进入副本')
    @operation_node(name='等待战斗画面加载', node_max_retry_times=60)
    def wait_battle_screen(self) -> OperationRoundResult:
        self.chosen_team = True
        screen = self.screenshot()
        return self.round_by_find_area(screen, '战斗画面', '按键-普通攻击',
                                       retry_wait=0.5)

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='模拟按键')
    def run_key_sim(self) -> OperationRoundResult:
        op = KeySimRunner(self.ctx, '真拿命验收')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='模拟按键')
    @operation_node(name='通关交互', node_max_retry_times=10)
    def interact_after_mission(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '真拿命验收', '对话人')
        if result.is_success:
            return self.round_success()

        self.ctx.controller.interact(press=True, press_time=0.2, release=True)

        return self.round_retry(wait=1)

    @node_from(from_name='通关交互')
    @operation_node(name='对话', node_max_retry_times=30)
    def talk_after_mission(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '战斗画面', '战斗结果-完成')
        if result.is_success:
            return self.round_success(wait=1)

        # 有选项就点选项
        area = self.ctx.screen_loader.get_area('真拿命验收', '对话选项')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        for ocr_result, mrl in ocr_result_map.items():
            to_click = mrl.max.center + area.left_top
            self.ctx.controller.click(to_click)
            return self.round_wait(status=ocr_result, wait=1)

        # 一直点击到出现完成按钮
        self.round_by_click_area('菜单', '返回')

        return self.round_retry(wait=1)

    @node_from(from_name='对话')
    @operation_node(name='完成', node_max_retry_times=60)
    def click_finished(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, 'HDD', '街区')
        if result.is_success:
            self.is_over_night = False
            self.run_record.add_times()
            return self.round_success(result.status)

        # 一直点击直到出现街区
        result = self.round_by_find_and_click_area(screen, '战斗画面', '战斗结果-完成')
        if result.is_success:
            return self.round_wait(result.status, wait=0.5)

        # 过夜提醒的对话比较多 不进行识别 不断点击空白直到返回大世界
        result = self.round_by_find_area(screen, '大世界', '信息')
        if result.is_success:
            self.is_over_night = True
            self.run_record.add_times()
            return self.round_success(result.status)

        self.round_by_click_area('HDD', '空白')

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='完成')
    @node_from(from_name='点击退出战斗确认')
    @operation_node(name='检查运行次数')
    def check_times(self) -> OperationRoundResult:
        self.run_record.check_and_update_status()
        if self.run_record.is_finished_by_times():
            return self.round_success(LifeOnLineApp.STATUS_TIMES_FINISHED)
        else:
            if self.is_over_night:
                return self.round_success(LifeOnLineApp.STATUS_CONTINUE_OVER_NIGHT)
            else:
                return self.round_success(LifeOnLineApp.STATUS_CONTINUE)

    @node_from(from_name='检查运行次数', status=STATUS_TIMES_FINISHED)
    @operation_node(name='返回大世界')
    def back_to_world(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='通关交互', success=False)
    @operation_node(name='交互失败')
    def fail_to_interact(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '恶名狩猎', '退出战斗')
        if result.is_success:
            return self.round_success(wait=1)  # 稍微等一下让按钮可按

        result = self.round_by_click_area('战斗画面', '菜单')
        if result.is_success:
            return self.round_wait(result.status, wait=2)
        else:
            return self.round_fail(result.status)

    @node_from(from_name='交互失败')
    @operation_node(name='点击退出战斗')
    def click_exit_battle(self) -> OperationRoundResult:
        screen = self.screenshot()

        return self.round_by_find_and_click_area(screen, '恶名狩猎', '退出战斗',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击退出战斗')
    @operation_node(name='点击退出战斗确认')
    def click_exit_battle_confirm(self) -> OperationRoundResult:
        screen = self.screenshot()

        return self.round_by_find_and_click_area(screen, '恶名狩猎', '退出战斗-确认',
                                                 success_wait=5, retry_wait=1)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = LifeOnLineApp(ctx)
    app.execute()

if __name__ == '__main__':
    __debug()
