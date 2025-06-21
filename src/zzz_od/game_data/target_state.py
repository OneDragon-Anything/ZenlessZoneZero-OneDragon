from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any


class TargetCheckWay(Enum):
    """
    定义如何解读CV流水线返回的结果
    """

    CONTOUR_COUNT_IN_RANGE = "contour_count_in_range"
    CONNECTED_AREA_WIDTH_RATIO = "connected_area_width_ratio"
    CONNECTED_AREA_LENGTH_RATIO = "connected_area_length_ratio"
    TEMPLATE_MATCH_CONFIDENCE = "template_match_confidence"
    OCR_RESULT_AS_NUMBER = "ocr_result_as_number"
    OCR_TEXT_CONTAINS = "ocr_text_contains"
    CONTOUR_LENGTH_AS_RATIO = "contour_length_as_ratio"  # 新增：轮廓长度比例
    MAP_CONTOUR_LENGTH_TO_PERCENT = "map_contour_length_to_percent"
    DIRECT_RETURN = "direct_return"  # 新增：直接返回指定结果，用于测试


@dataclass
class TargetStateDef:
    """
    状态解读器：定义如何从一份CV结果中提取一个具体的状态。
    """

    state_name: str
    check_way: TargetCheckWay
    check_params: Dict[str, Any] = field(default_factory=dict)
    # 当状态未命中时，是否发送False来清除状态
    clear_on_miss: bool = False


@dataclass
class DetectionTask:
    """
    检测任务组：定义一次完整的、可调度的检测活动。
    """

    task_id: str
    pipeline_name: str
    state_definitions: List[TargetStateDef]
    enabled: bool = True
    interval: float = 1.0
    is_async: bool = False
    # 用于动态频率的特殊配置
    dynamic_interval_config: dict = field(default_factory=dict)


# 状态检测任务注册表
# 这是未来扩展的唯一修改点
DETECTION_TASKS: List[DetectionTask] = [
    # 任务1: 锁定检测
    DetectionTask(
        task_id="lock_on",
        pipeline_name="lock-far",
        interval=0,  # 默认不检测，由yml配置 > 0 的值来启用
        dynamic_interval_config={
            "state_to_watch": "目标-近距离锁定",
            "interval_if_state": 1.0,  # 锁定时用1秒间隔
            "interval_if_not_state": 0,
            "kwarg_if_state": "check_lock_interval_locked",
            "kwarg_if_not_state": "check_lock_interval_unlocked",
        },
        state_definitions=[
            TargetStateDef(
                "目标-近距离锁定",
                TargetCheckWay.CONTOUR_COUNT_IN_RANGE,
                {"min_count": 2},
                clear_on_miss=False,
            ),
        ],
    ),
    # 任务2: 异常状态检测 (一次OCR，多次解读)
    DetectionTask(
        task_id="abnormal_statuses",
        pipeline_name="ocr-abnormal",
        interval=0,  # 默认不检测，由yml配置 > 0 的值来启用
        is_async=True,
        state_definitions=[
            TargetStateDef(
                "目标-异常-灼烧",
                TargetCheckWay.OCR_TEXT_CONTAINS,
                {"contains": ["烧"], "mode": "any"},
                clear_on_miss=False,
            ),
            TargetStateDef(
                "目标-异常-冻结",
                TargetCheckWay.OCR_TEXT_CONTAINS,
                {"contains": ["冻", "结"], "mode": "any"},
                clear_on_miss=False,
            ),
            TargetStateDef(
                "目标-异常-霜灼",
                TargetCheckWay.OCR_TEXT_CONTAINS,
                {"contains": ["霜"], "mode": "any"},
                clear_on_miss=False,
            ),
            TargetStateDef(
                "目标-异常-感电",
                TargetCheckWay.OCR_TEXT_CONTAINS,
                {"contains": ["感", "电"], "mode": "any"},
                clear_on_miss=False,
            ),
            TargetStateDef(
                "目标-异常-碎冰",
                TargetCheckWay.OCR_TEXT_CONTAINS,
                {"contains": ["碎", "冰"], "mode": "any"},
                clear_on_miss=False,
            ),
            TargetStateDef(
                "目标-异常-侵蚀",
                TargetCheckWay.OCR_TEXT_CONTAINS,
                {"contains": ["侵", "蚀"], "mode": "any"},
                clear_on_miss=False,
            ),
            TargetStateDef(
                "目标-异常-强击",
                TargetCheckWay.OCR_TEXT_CONTAINS,
                {"contains": ["强", "击"], "mode": "any"},
                clear_on_miss=False,
            ),
        ],
    ),
    # 任务3: Boss状态检测 (一次OCR，混合解读)
    DetectionTask(
        task_id="boss_status",
        pipeline_name="boss_stun",
        interval=0.5,
        enabled=False,  # 有更好的检测方法哦
        is_async=True,
        state_definitions=[
            TargetStateDef("目标-失衡值", TargetCheckWay.OCR_RESULT_AS_NUMBER),
            TargetStateDef(
                "目标-强敌", TargetCheckWay.OCR_TEXT_CONTAINS, {"contains": "强敌"}
            ),
        ],
    ),
    # 任务4: 使用长度映射法检测强敌失衡值
    DetectionTask(
        task_id="boss_stun_by_length",
        pipeline_name="boss_stun_line",  # 使用您指定的流水线
        interval=0.5,
        is_async=True,
        state_definitions=[
            TargetStateDef(
                "强敌-失衡值",
                TargetCheckWay.MAP_CONTOUR_LENGTH_TO_PERCENT,
                check_params={
                    "full_value_length": 100,  # 100% 对应的像素长度
                    "empty_value_length": 0,  # 0% 对应的像素长度
                },
                clear_on_miss=True,
            ),
        ],
    ),
]
