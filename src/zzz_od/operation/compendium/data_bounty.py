from typing import ClassVar

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class DataBounty(ZOperation):
    """
    检测数据悬赏的操作
    在快捷手册-训练界面检测黄条，识别数据悬赏关键词和剩余次数
    """

    STATUS_DATA_BOUNTY_AVAILABLE: ClassVar[str] = '数据悬赏可用'
    STATUS_NO_DATA_BOUNTY: ClassVar[str] = '无数据悬赏'

    def __init__(self, ctx: ZContext):
        ZOperation.__init__(self, ctx, op_name='检测数据悬赏')
        self.data_bounty_count: int | None = None
        self.data_bounty_max: int | None = None

    @operation_node(name='检测数据悬赏', is_start_node=True)
    def check_data_bounty(self) -> OperationRoundResult:
        """
        检测是否存在数据悬赏
        识别黄条区域内的数据悬赏关键词和类似5/5的数量格式
        """
        # 首先检测黄条区域是否有特定颜色
        area = self.ctx.screen_loader.get_area('数据悬赏', '黄条区域')
        if area is None:
            log.info('未找到数据悬赏区域配置')
            return self.round_success(DataBounty.STATUS_NO_DATA_BOUNTY)

        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)

        # 使用OCR识别黄条区域的文本
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        log.debug(f'数据悬赏OCR结果: {ocr_result_map}')

        # 检查是否包含"数据悬赏"关键词
        has_data_bounty_keyword = False
        for ocr_text in ocr_result_map:
            if '数据悬赏' in ocr_text or str_utils.find_by_lcs('数据悬赏', ocr_text, percent=0.6):
                has_data_bounty_keyword = True
                break

        if not has_data_bounty_keyword:
            log.info('未检测到数据悬赏关键词')
            return self.round_success(DataBounty.STATUS_NO_DATA_BOUNTY)

        # 检测类似5/5的数量格式
        count_found = False
        for ocr_text in ocr_result_map:
            # 尝试解析 x/y 格式
            if '/' in ocr_text:
                parts = ocr_text.split('/')
                if len(parts) == 2:
                    try:
                        # 提取数字部分
                        current_digits = ''.join(filter(str.isdigit, parts[0]))
                        total_digits = ''.join(filter(str.isdigit, parts[1]))
                        # 确保有数字可以解析
                        if current_digits and total_digits:
                            current = int(current_digits)
                            total = int(total_digits)
                            if current > 0 and total > 0:
                                self.data_bounty_count = current
                                self.data_bounty_max = total
                                count_found = True
                                log.info(f'数据悬赏剩余次数: {current}/{total}')
                                break
                    except (ValueError, TypeError):
                        continue

        if not count_found:
            # 如果没有找到具体数量，但有关键词，默认设置为1次
            self.data_bounty_count = 1
            self.data_bounty_max = 1
            log.info('检测到数据悬赏关键词，但未识别到具体次数，默认设置为1次')

        if self.data_bounty_count is not None and self.data_bounty_count > 0:
            log.info(f'数据悬赏可用，剩余次数: {self.data_bounty_count}')
            return self.round_success(DataBounty.STATUS_DATA_BOUNTY_AVAILABLE)
        else:
            log.info('数据悬赏次数为0或无法识别')
            return self.round_success(DataBounty.STATUS_NO_DATA_BOUNTY)


def __debug_data_bounty():
    """
    测试数据悬赏识别
    """
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('0')
    area = ctx.screen_loader.get_area('数据悬赏', '黄条区域')
    part = cv2_utils.crop_image_only(screen, area.rect)
    ocr_result = ctx.ocr.run_ocr(part)
    print(ocr_result)


if __name__ == '__main__':
    __debug_data_bounty()
