from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / 'src'
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from one_dragon.base.screen.template_info import TemplateInfo
from one_dragon.utils import cv2_utils
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum


@dataclass(frozen=True)
class StateTemplate:
    state_name: str
    template: TemplateInfo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='采集代理人配置中状态区域的 HSV 连续区间。')
    parser.add_argument('--agent', required=True, help='AgentEnum 中的代理人 ID，例如 remielle。')
    parser.add_argument('--duration', type=float, default=1, help='总采集时长秒数。默认 1。')
    parser.add_argument('--interval', type=float, default=0.02, help='相邻截图的最小间隔秒数。默认 0.02。')
    return parser.parse_args()


def get_agent(agent_id: str):
    for agent_enum in AgentEnum:
        if agent_enum.value.agent_id == agent_id:
            return agent_enum.value
    raise ValueError(f'未找到代理人配置 {agent_id}。')


def load_state_templates(agent_id: str) -> list[StateTemplate]:
    agent = get_agent(agent_id)
    if not agent.state_list:
        raise ValueError(f'代理人 {agent_id} 没有状态配置。')

    template_root = PROJECT_ROOT / 'assets' / 'template' / 'agent_state'
    state_templates: list[StateTemplate] = []
    for state_def in agent.state_list:
        for template_dir in sorted(template_root.glob(f'{state_def.template_id}_*')):
            template = TemplateInfo('agent_state', template_dir.name)
            rect = template.get_template_rect_by_point()
            if rect is None or rect.width <= 0 or rect.height <= 0:
                print(f'跳过无效状态区域：{template.template_id}')
                continue
            state_templates.append(StateTemplate(state_def.state_name, template))

    if not state_templates:
        raise ValueError(f'代理人 {agent_id} 的状态配置没有可采集的 agent_state 模板。')
    return state_templates


def get_mask(template: TemplateInfo, screen: np.ndarray) -> np.ndarray:
    if template.mask is not None:
        return template.mask

    template.screen_image = screen
    mask = template.get_template_mask_by_screen_point()
    if mask is None:
        raise ValueError(f'模板 {template.template_id} 无法生成几何掩码。')
    return mask


def collect_template_hsv(screen: np.ndarray, template: TemplateInfo) -> np.ndarray:
    rect = template.get_template_rect_by_point()
    if rect is None:
        return np.empty((0, 3), dtype=np.uint8)

    part = cv2_utils.crop_image_only(screen, rect)
    mask = get_mask(template, screen)
    if part.shape[:2] != mask.shape[:2]:
        raise ValueError(f'模板 {template.template_id} 的掩码尺寸与状态区域不一致。')

    return cv2.cvtColor(part, cv2.COLOR_RGB2HSV)[mask > 0]


def merge_continuous_ranges(values: set[int]) -> list[tuple[int, int]]:
    if not values:
        return []

    ranges: list[tuple[int, int]] = []
    start = end = min(values)
    for value in sorted(values)[1:]:
        if value == end + 1:
            end = value
            continue
        ranges.append((start, end))
        start = end = value
    ranges.append((start, end))
    return ranges


def format_ranges(ranges: list[tuple[int, int]]) -> str:
    return ', '.join(f'{start}-{end}' for start, end in ranges) if ranges else '无样本'


def main() -> None:
    args = parse_args()
    if args.duration <= 0:
        raise ValueError('--duration 必须大于 0。')
    if args.interval <= 0:
        raise ValueError('--interval 必须大于 0。')

    state_templates = load_state_templates(args.agent)
    context = ZContext()
    context.init()
    if not context.controller.is_game_window_ready:
        raise RuntimeError('游戏窗口未就绪。')

    state_values: dict[str, list[set[int]]] = defaultdict(lambda: [set(), set(), set()])
    frame_count = 0
    end_at = time.monotonic() + args.duration
    print(f'开始采集 {args.agent} {args.duration} 秒。')

    try:
        while time.monotonic() < end_at:
            frame_started_at = time.monotonic()
            _, screen = context.controller.screenshot()
            if screen is None:
                continue

            frame_count += 1
            for state_template in state_templates:
                hsv_pixels = collect_template_hsv(screen, state_template.template)
                for channel_index in range(3):
                    state_values[state_template.state_name][channel_index].update(
                        int(value) for value in hsv_pixels[:, channel_index]
                    )

            elapsed = time.monotonic() - frame_started_at
            if elapsed < args.interval:
                time.sleep(args.interval - elapsed)
    finally:
        context.controller.cleanup_after_app_shutdown()

    print(f'采集完成：{frame_count} 帧')
    for state_name, channels in state_values.items():
        print(f'{state_name}:')
        print(f'  H: {format_ranges(merge_continuous_ranges(channels[0]))}')
        print(f'  S: {format_ranges(merge_continuous_ranges(channels[1]))}')
        print(f'  V: {format_ranges(merge_continuous_ranges(channels[2]))}')


if __name__ == '__main__':
    main()
