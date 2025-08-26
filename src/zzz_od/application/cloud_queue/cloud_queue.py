from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class CloudGameQueue(ZOperation):
    """
    云游戏排队操作类
    """

    def __init__(self, ctx: ZContext):
        ZOperation.__init__(self, ctx, op_name=gt('云游戏排队'))

    @node_from(from_name='画面识别', status='国服PC云-点击空白区域关闭')
    @operation_node(name='画面识别', node_max_retry_times=60, is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '云游戏', '国服PC云-切换窗口')
        if result.is_fail:
            return self.round_retry(status='未知画面', wait=1)

        result = self.round_by_find_and_click_area(self.last_screenshot, '云游戏', '国服PC云-点击空白区域关闭')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_area(self.last_screenshot, '云游戏', '国服PC云-排队中')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(self.last_screenshot, '云游戏', '国服PC云-开始游戏')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_area(self.last_screenshot, '打开游戏', '点击进入游戏')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_area(self.last_screenshot, '大世界', '信息')
        if result.is_success:
            return self.round_success(result.status)

        return self.round_retry(status='未知画面', wait=1)

    @node_from(from_name='画面识别', status='国服PC云-开始游戏')
    @operation_node(name='国服PC云-插队或排队')
    def cn_pc_cloud_start_or_queue(self) -> OperationRoundResult:
        """
        国服PC云-插队或排队
        :return:
        """
        screen = self.last_screenshot
        result_bang = self.round_by_find_area(screen, '云游戏', '国服PC云-邦邦点快速队列')
        result_exit = self.round_by_find_area(screen, '云游戏', '国服PC云-排队中')
        if result_bang.is_success:
            if self.ctx.cloud_queue_config.prefer_bangbang_points:
                # 识别"国服PC云-插队"区域
                result = self.round_by_find_and_click_area(screen, '云游戏', '国服PC云-邦邦点快速队列')
                if result.is_success:
                    return self.round_success(result.status, wait=1)
            else:
                result = self.round_by_find_and_click_area(screen, '云游戏', '国服PC云-普通队列')
                if result.is_success:
                    return self.round_success(result.status, wait=1)
        elif result_exit.is_success:
            return self.round_success(result_exit.status, wait=1)

        return self.round_retry(status='未知画面', wait=1)

    @node_from(from_name='国服PC云-插队或排队', status='国服PC云-排队中')
    @node_from(from_name='国服PC云-插队或排队', status='国服PC云-邦邦点快速队列')
    @node_from(from_name='国服PC云-插队或排队', status='国服PC云-普通队列')
    @node_from(from_name='画面识别', status='国服PC云-排队中')
    @node_from(from_name='国服PC云-排队中转', status='排队中转')
    @operation_node(name='国服PC云-排队')
    def cn_pc_cloud_queue(self) -> OperationRoundResult:
        """
        国服PC云-排队
        :return:
        """
        # OCR识别"国服PC云-排队人数"区域的值
        queue_count_text = ""
        area = self.ctx.screen_loader.get_area('云游戏', '国服PC云-排队人数')
        if area is not None:
            ocr_result = self.round_by_ocr_text(self.last_screenshot, area, area.color_range)
            if ocr_result.is_success:
                queue_count_text = " ".join(ocr_result.data.keys())

        # OCR识别"国服PC云-预计等待时间"区域的值
        wait_time_text = ""
        area = self.ctx.screen_loader.get_area('云游戏', '国服PC云-预计等待时间')
        if area is not None:
            ocr_result = self.round_by_ocr_text(self.last_screenshot, area, area.color_range)
            if ocr_result.is_success:
                wait_time_text = " ".join(ocr_result.data.keys())

        # 将识别到的值通过log输出
        log.info(f"国服PC云排队信息 - 排队人数: {queue_count_text}, 预计等待时间: {wait_time_text}分钟")

        # 检查是否能识别到"点击进入游戏"区域
        enter_game_result = self.round_by_find_area(self.last_screenshot, '打开游戏', '点击进入游戏')
        if enter_game_result.is_success:
            # 如果识别到"点击进入游戏"，则退出循环，返回成功 由EnterGame来进入游戏
            return self.round_success(status='点击进入游戏', wait=1)
        else:
            # 如果未识别到"点击进入游戏"，则返回等待状态，等待一段时间后切换到第二个节点继续循环
            return self.round_wait(status='等待排队', wait=10)

    @node_from(from_name='国服PC云-排队', status='等待排队')
    @operation_node(name='国服PC云-排队中转')
    def cn_pc_cloud_queue_transfer(self) -> OperationRoundResult:
        """
        国服PC云-排队中转节点
        :return:
        """
        # 仅作为中转，直接切换回第一个节点继续处理
        return self.round_wait(status='排队中转', wait=1)

def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.start_running()
    ctx.init_ocr()
    op = CloudGameQueue(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
