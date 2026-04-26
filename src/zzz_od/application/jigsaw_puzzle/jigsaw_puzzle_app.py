import time

import cv2
import numpy as np

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils
from one_dragon.yolo import log_utils
from zzz_od.application.jigsaw_puzzle import jigsaw_puzzle_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class JigSawPuzzleApp(ZApplication):

    def __init__(self, ctx: ZContext):
        """
        拼图
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=jigsaw_puzzle_const.APP_ID,
            op_name=jigsaw_puzzle_const.APP_NAME,
        )
        self.raw_img: np.ndarray | None = None
        self.pieces: list[np.ndarray, Rect] = []  # 拼图碎片
        self.puzzle_rect: Rect = Rect(999, 164, 1840, 1000)  # 拼图区域
        self.h_lines: list[int] = []  # 识别出的竖线
        self.v_lines: list[int] = []  # 识别出的横线
        self.forbidden_rects: list[Rect] = []
        self.start_piece: int = 0  # 当前进行到哪一块了
        self.moved: bool = False  # 将 start_piece 重置为0之后有没有移动过图片 用于结束判断

    @node_from(from_name='移动图片', success=False)
    @operation_node(name='分析图片', is_start_node=True)
    def click_raw_pic(self) -> OperationRoundResult:
        cropped_image = cv2_utils.crop_image(self.last_screenshot, self.puzzle_rect)[0]

        # 1. 检测网格线
        h_lines, v_lines = detect_grid_lines(cropped_image)
        print(f"原始水平线：{h_lines}")
        print(f"原始垂直线：{v_lines}")

        # 2. 合并重复线
        self.h_lines = merge_lines(h_lines)
        self.v_lines = merge_lines(v_lines)
        print(f"合并后水平线：{h_lines}")
        print(f"合并后垂直线：{v_lines}")

        # 3. 切片拼图块
        self.pieces = slice_puzzle_pieces(cropped_image, h_lines, v_lines, self.puzzle_rect.left_top)
        print(f"切片完成，共 {len(self.pieces)} 块拼图")
        # # 4. 保存切片结果（可选）
        # for idx, piece in enumerate(self.pieces):
        #     cv2_utils.save_image(piece[0], f"Y:\\piece_{idx}.png")

        # 点击原图
        self.ctx.controller.click(pos=Point(910, 949))
        time.sleep(0.2)
        self.raw_img = cv2_utils.crop_image(self.screenshot(), self.puzzle_rect)[0]
        self.ctx.controller.click(pos=Point(910, 949))
        time.sleep(0.2)
        return self.round_success()

    @node_from(from_name='分析图片')
    @operation_node(name='移动图片')
    def move_img(self) -> OperationRoundResult:
        cropped_image = cv2_utils.crop_image(self.last_screenshot, self.puzzle_rect)[0]
        self.pieces = slice_puzzle_pieces(cropped_image, self.h_lines, self.v_lines, self.puzzle_rect.left_top)

        start_time = time.time()
        for i in range(1 + self.start_piece, 1 + len(self.pieces)):
            end_time = time.time()
            if end_time - start_time > 3:
                return self.round_fail('检测时间过长, 重置检测以加快速度')
            if i == len(self.pieces):
                if self.moved:
                    return self.round_success(wait=1)
                else:
                    self.start_piece = 0
                    self.moved = False
                    return self.round_wait()
            match_result: MatchResultList = cv2_utils.match_template(self.raw_img, self.pieces[i][0], 0.7, mask=None,
                                                                     only_best=True, ignore_inf=True)
            if match_result is not None and len(match_result) > 0:
                end_point: Point = match_result.arr[0].center.__add__(self.puzzle_rect.left_top)
                start_point: Point = self.pieces[i][1].center

                forbidden = False
                for i in range(len(self.forbidden_rects)):
                    if self.forbidden_rects[i].x1 == end_point.x \
                            and self.forbidden_rects[i].y1 == end_point.y \
                            and self.forbidden_rects[i].x2 == start_point.x \
                            and self.forbidden_rects[i].y2 == start_point.y:
                        forbidden = True
                        break
                if forbidden:
                    continue

                if abs(end_point.x - start_point.x) < 50 and abs(end_point.y - start_point.y) < 50:
                    continue
                log_utils.log.info(f'confidence = {match_result.arr[0].confidence}')
                self.ctx.controller.drag_to(start_point, end_point, duration=0.2)
                self.forbidden_rects.append(
                    Rect(end_point.x, end_point.y, start_point.x, start_point.y))
                self.start_piece = i
                self.moved = True
                return self.round_wait(wait=0.2)
        return self.round_success(wait=1)


def detect_grid_lines(img, threshold=100, min_line_length=100, max_line_gap=10):
    """
    检测图像中的水平和垂直线（拼图网格线）
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # 霍夫直线检测
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=threshold,
        minLineLength=min_line_length,
        maxLineGap=max_line_gap
    )

    horizontal_lines = []
    vertical_lines = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # 水平线（y坐标几乎不变）
            if abs(y1 - y2) < 5:
                horizontal_lines.append((y1 + y2) // 2)
            # 垂直线（x坐标几乎不变）
            elif abs(x1 - x2) < 5:
                vertical_lines.append((x1 + x2) // 2)

    # 去重并排序
    horizontal_lines = sorted(list(set(horizontal_lines)))
    vertical_lines = sorted(list(set(vertical_lines)))

    return horizontal_lines, vertical_lines


def merge_lines(lines, threshold=20):
    """
    合并靠得太近的线，减少重复
    """
    if not lines:
        return []
    merged = [lines[0]]
    for line in lines[1:]:
        if line - merged[-1] > threshold:
            merged.append(line)
    return merged


def slice_puzzle_pieces(img, horizontal_lines, vertical_lines, offset: Point) -> list[np.ndarray, Rect]:
    """
    根据网格线切片拼图块
    """
    pieces: list[np.ndarray, Rect] = []
    # 先加图像边界
    h, w = img.shape[:2]
    h_lines = [0] + horizontal_lines + [h]
    v_lines = [0] + vertical_lines + [w]

    # 按行、列切片
    for i in range(len(h_lines) - 2):
        if i == 0:
            continue
        y1, y2 = h_lines[i], h_lines[i + 1]
        for j in range(len(v_lines) - 2):
            if j == 0:
                continue
            x1, x2 = v_lines[j], v_lines[j + 1]
            piece = img[y1:y2, x1:x2]
            rect: Rect = Rect(x1, y1, x2, y2)
            rect.add_offset(offset)
            pieces.append([piece, rect])
    return pieces


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = JigSawPuzzleApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
