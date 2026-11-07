"""采集模板区域内、掩码覆盖到的像素颜色区间。

绝区零不在前台时跳过该轮，不截图、不计入统计。
"""

import argparse
import sys
import time
from pathlib import Path

# skill 脚本不在 src-layout 的包内 直接运行时要把项目源码目录放进 sys.path
_PROJECT_SRC = Path(__file__).resolve().parents[2] / 'src'
if str(_PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(_PROJECT_SRC))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from one_dragon.utils import cv2_utils  # noqa: E402


def format_tuple(values) -> str:
    """把 numpy 数组或元组格式化成 (a, b, c) 形式，去掉 numpy 包装"""
    return '(' + ', '.join(str(int(round(float(v)))) for v in values) + ')'


def fit_hue(h_values) -> tuple[int, int]:
    """H 通道是 0~179 的循环量 用最大间隙法求中心与能覆盖全部采样的最小容差"""
    hues = np.unique(np.asarray(h_values, dtype=np.int32) % 180)
    if hues.size == 0:
        return 0, 90
    if hues.size == 1:
        return int(hues[0]), 0

    # 排序后的相邻差 以及首尾接缝处的那一段
    gaps = np.diff(np.concatenate([hues, [hues[0] + 180]]))
    gap_idx = int(np.argmax(gaps))
    span_start = int(hues[(gap_idx + 1) % hues.size])
    span = 180 - int(gaps[gap_idx])
    center = int((span_start + span / 2) % 180)
    return center, int(np.ceil(span / 2))


def fit_linear(lo: float, hi: float) -> tuple[int, int]:
    """S 与 V 是线性量 直接取中点与半宽"""
    lo_i, hi_i = int(round(lo)), int(round(hi))
    return (lo_i + hi_i) // 2, int(np.ceil((hi_i - lo_i) / 2))


def make_setting(h_values, s_range, v_range) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """把出现过的 H 值与 S/V 区间换算成 hsv_color 与 hsv_color_diff"""
    h_center, h_diff = fit_hue(h_values)
    s_center, s_diff = fit_linear(*s_range)
    v_center, v_diff = fit_linear(*v_range)
    return (h_center, s_center, v_center), (h_diff, s_diff, v_diff)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='采集模板颜色区间')
    parser.add_argument('template_id', help='模板 id，例如 remielle_voidflare_3_1')
    parser.add_argument('--sub-dir', default='agent_state', help='模板子目录，默认 agent_state')
    parser.add_argument('--duration', type=float, default=5, help='采集秒数，默认 5，0 表示一直采到 Ctrl+C')
    parser.add_argument('--interval', type=float, default=0.1, help='采样间隔秒，默认 0.1')
    parser.add_argument('--print-interval', type=float, default=1.0, help='进度打印间隔秒，默认 1')
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from zzz_od.context.zzz_context import ZContext

    ctx = ZContext()
    if ctx.controller is None:
        ctx.init_controller()
    if ctx.controller is None:
        print('无法初始化控制器，确认游戏平台配置为 PC')
        return 1
    template = ctx.template_loader.get_template(args.sub_dir, args.template_id)
    if template is None:
        print(f'模板不存在: {args.sub_dir}/{args.template_id}')
        return 1

    rect = template.get_template_rect_by_point()
    if rect is None:
        print('模板点位不足，无法得到区域')
        return 1

    mask: np.ndarray | None = template.mask
    if mask is not None and mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_RGB2GRAY)
    mask_source = 'mask.png' if mask is not None else '点位'

    print(f'模板: {args.sub_dir}/{args.template_id}')
    print(f'区域: ({rect.x1}, {rect.y1}) - ({rect.x2}, {rect.y2})  {rect.width}x{rect.height}')
    print(f'掩码来源: {mask_source}' + (f'  覆盖 {mask.mean() / 255:.3f}' if mask is not None else '  待首帧生成'))
    print('等待绝区零切到前台...')

    rgb_min = np.full(3, 255, dtype=np.int16)
    rgb_max = np.zeros(3, dtype=np.int16)
    hsv_min = np.full(3, 255, dtype=np.int16)
    hsv_max = np.zeros(3, dtype=np.int16)
    h_hist = np.zeros(180, dtype=np.int64)  # 只保留出现过的 H 值 长时间采集也不涨内存
    frame_cnt = 0
    pixel_cnt = 0
    skip_cnt = 0
    active_time = 0.0  # 只累计绝区零在前台的时长 后台等待不算采集
    last_tick = time.time()
    last_print = 0.0

    try:
        while True:
            now = time.time()
            win_active = ctx.controller.game_win.is_win_active
            if win_active:
                active_time += now - last_tick
            last_tick = now
            if args.duration > 0 and active_time >= args.duration:
                break

            if not win_active:
                skip_cnt += 1
                if skip_cnt == 1:
                    print('绝区零不在前台，暂停采集')
                time.sleep(args.interval)
                continue
            if skip_cnt > 0:
                print(f'已回到前台，恢复采集（之前跳过 {skip_cnt} 轮）')
                skip_cnt = 0

            _, screen = ctx.controller.screenshot()
            if screen is None:
                time.sleep(args.interval)
                continue

            part = cv2_utils.crop_image_only(screen, rect)
            if mask is None:
                template.screen_image = screen
                mask = template.get_template_mask_by_screen_point()
                if mask is None:
                    print('点位无法生成掩码，检查模板形状与点位数')
                    return 1
                print(f'已按点位生成掩码，覆盖 {mask.mean() / 255:.3f}')
            if part.shape[0] != mask.shape[0] or part.shape[1] != mask.shape[1]:
                print(f'区域尺寸 {part.shape[:2]} 与掩码 {mask.shape[:2]} 不一致，检查模板点位')
                return 1

            valid = mask > 127
            pixels = part[valid]
            if pixels.size == 0:
                time.sleep(args.interval)
                continue

            hsv = cv2.cvtColor(part, cv2.COLOR_RGB2HSV)[valid]

            rgb_min = np.minimum(rgb_min, pixels.min(axis=0))
            rgb_max = np.maximum(rgb_max, pixels.max(axis=0))
            hsv_min = np.minimum(hsv_min, hsv.min(axis=0))
            hsv_max = np.maximum(hsv_max, hsv.max(axis=0))
            h_hist += np.bincount(hsv[:, 0].ravel(), minlength=180)
            pixel_cnt += pixels.shape[0]
            frame_cnt += 1

            if active_time - last_print >= args.print_interval:
                last_print = active_time
                cur_color, cur_diff = make_setting(
                    np.nonzero(h_hist)[0],
                    (float(hsv_min[1]), float(hsv_max[1])),
                    (float(hsv_min[2]), float(hsv_max[2])),
                )
                print(f'[{active_time:5.1f}s] 帧 {frame_cnt}  '
                      f'RGB {format_tuple(rgb_min)}~{format_tuple(rgb_max)}  '
                      f'HSV 中心{format_tuple(cur_color)} 容差{format_tuple(cur_diff)}')

            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass

    if frame_cnt == 0:
        print('没有采到任何帧')
        return 1

    print()
    print(f'采集完成  帧数 {frame_cnt}  像素 {pixel_cnt}  有效采集 {active_time:.1f}s')

    color, diff = make_setting(
        np.nonzero(h_hist)[0],
        (float(hsv_min[1]), float(hsv_max[1])),
        (float(hsv_min[2]), float(hsv_max[2])),
    )

    print()
    print('可直接填入 AgentStateDef（覆盖本次每一个采样点）：')
    print(f'  hsv_color={color}')
    print(f'  hsv_color_diff={diff}')

    is_rgb_channel_ok = True
    for idx in range(3):
        if rgb_max[idx] - rgb_min[idx] > 90:
            is_rgb_channel_ok = False
    if is_rgb_channel_ok:
        print('走 RGB 模式的话：')
        print(f'  lower_color={format_tuple(rgb_min)}')
        print(f'  upper_color={format_tuple(rgb_max)}')
    else:
        print('RGB 各通道跨度偏大 不建议走 RGB 模式 用上面的 HSV')
    print()
    print(f'参考 RGB 区间 {format_tuple(rgb_min)}~{format_tuple(rgb_max)}')
    print(f'参考 S 区间 {int(hsv_min[1])}~{int(hsv_max[1])}  V 区间 {int(hsv_min[2])}~{int(hsv_max[2])}')
    print('H 是 0~179 的循环量 不适用上下限 直接看上面的 hsv_color 与 hsv_color_diff')
    return 0


if __name__ == '__main__':
    sys.exit(main())
