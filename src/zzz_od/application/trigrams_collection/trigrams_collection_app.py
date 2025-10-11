import time

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.trigrams_collection import trigrams_collection_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.transport import Transport


class TrigramsCollectionApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=trigrams_collection_const.APP_ID,
            op_name=gt(trigrams_collection_const.APP_NAME),
            need_notify=True,
        )
        self.claim_reward: bool = False  # 是否已获取卦象

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        op = Transport(self.ctx, '澄辉坪', '阿朔', wait_at_last=True)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='移动交互')
    def move_and_interact(self) -> OperationRoundResult:
        """
        传送之后 往前移动一下 方便交互
        :return:
        """
        # self.ctx.controller.move_w(press=True, press_time=1, release=True)
        # time.sleep(1)

        self.ctx.controller.interact(press=True, press_time=0.2, release=True)
        time.sleep(3)

        return self.round_success()

    @node_from(from_name='移动交互')
    @operation_node(name='获取卦象', node_max_retry_times=5)
    def get_trigram(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)

        target_word_list: list[str] = [
            '卦象集录',  # 外层还没开卦象的时候
            '滑动屏幕以获取卦象',  # 需要有这个词 防止画面出现"已领取"也匹配到"领取"
            '确认',  # 获取卦象后 or 已完成同类活动 issue #1027
        ]
        word, mrl = ocr_utils.match_word_list_by_priority(ocr_result_map, target_word_list)
        if word == '卦象集录':
            if self.claim_reward:
                return self.round_success(status=word)
            else:
                result = self.round_by_click_area('卦象集录', '区域-获取卦象')
                return self.round_wait(status=word, wait=1)
        elif word == '滑动屏幕以获取卦象':
            start = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
            end = start + Point(-800, 0)
            self.ctx.controller.drag_to(start=start, end=end, duration=0.2)
            return self.round_wait(status=word, wait=1)
        elif word == '确认':
            self.claim_reward = True
            self.ctx.controller.click(mrl.max.center)
            return self.round_wait(status=word, wait=1)

        return self.round_by_click_area('卦象集录', '区域-开卦象',
                                        success_wait=1)

    @node_from(from_name='获取卦象')
    @operation_node(name='结束后返回')
    def back_at_last(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = TrigramsCollectionApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()