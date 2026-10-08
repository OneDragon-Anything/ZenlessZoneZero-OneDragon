"""正式贝果任务的使用提示；不参与操作、计数或状态流转。"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from one_dragon.utils import debug_utils
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from zzz_od.application.bagel.bagel_config import BagelConfig


GUIDE_URL: str = 'https://github.com/Cora093/ZenlessZoneZero-OneDragon/blob/bagel/docs/develop/zzz/application/bagel_usage.md'
ROLE_HINT: str = '请尽量不要使用有特殊移动方式的角色（如星见雅、叶瞬光等）。这类移动可能影响导航与定位的稳定性。'
LOADOUT_TITLE: str = '首次入场会卸下背包物品身上装备'
LOADOUT_HINT: str = '首次入场前，程序会将背包和安全箱内的物品放入仓库，再卸下已装备物品。'
CLEAN_HINT: str = '清理仓库时，程序会按出售方案自动出售物品。出售范围包含已有库存。'
NO_CLEAN_HINT: str = '程序只将物品放入仓库，不出售物品。首次入场仍会清空携带物。结算后仓库仍满时，任务会停止。'
SUCCESS_HINT: str = '成功入仓并完成结算后计数。失败局和空箱局不计成功。填 0 不限次数，异常时仍可能停止。'
RETRY_HINT: str = '局内失败后最多额外重开的次数。成功或暂停恢复后不清零。填 0 时只结算，不重开。'
CLEAN_SWITCH_HINT: str = '开启后，程序在入仓后按方案出售物品。关闭后，不自动出售清理仓库。'
DEFAULT_SALE_HINT: str = '默认出售贵重物品、战术棱镜和其他物品中的 C/B/A/S 品质。默认不出售 Z 品质、装备、战术道具和门禁卡。'
CUSTOM_SALE_HINT: str = '请至少选择一种类型和一种品质。物品同时符合两项条件时，程序才会出售。选择 Z 品质或装备等类型后，相应物品也可能被出售。'
INCOMPLETE_SALE_HINT: str = '类型或品质未选择，任务无法启动。请至少选择一种类型和一种品质。'
ACCOUNT_HINT: str = '这些设置只用于当前账号和应用组。切换账号或应用组后，请检查次数、清理开关和出售方案。'
LOCATION_WAIT_HINT: str = '小地图暂时无法定位。程序已停止移动，正在读取新截图。'
FEEDBACK_HINT: str = '反馈时，请提供停止原因、发生时间、所用角色、次数设置、清理开关、出售方案和相关日志。如果程序保存了现场截图，请一并提供。'


def log_start(config: BagelConfig) -> None:
    """仅在配置和资源校验通过后说明本次将执行的动作。"""
    limit = str(config.max_success_rounds) if config.max_success_rounds else '不限'
    log.info('即将进入雅努斯高危。成功次数上限：%s。整体重试次数上限：%s。', limit, config.max_failure_retries)
    if config.auto_clean_warehouse:
        names = '、'.join(name.removeprefix('筛选-') for name in config.clean_filter_areas())
        log.info('清理仓库已开启。出售范围：%s。类型和品质须同时符合。已有库存也会出售。', names)
    else:
        log.info('清理仓库已关闭。程序只入仓，不出售物品。')
    log.info('%s随后核对零携带和零投资。', LOADOUT_HINT)


def stop_guidance(status: str | None) -> str:
    """依据已返回的原因补充处理建议，不改变成功与失败判定。"""
    reason = status or ''
    if '仅部分入仓' in reason and '安全箱' in reason:
        return ('部分物品已入仓，安全箱尚未清空。程序已停止重复点击「放入仓库」。'
                '本局不计成功，也不会继续清理仓库或开始下一局。'
                '请核对安全箱中的剩余物品，再检查仓库中已收到的物品。')
    if '仅部分入仓' in reason:
        return ('部分物品已入仓，携带物尚未清空。程序已停止重复点击「放入仓库」。'
                '本局不计成功，也不会继续清理仓库或开始下一局。'
                '请核对安全箱和背包中的剩余物品，再检查仓库中已收到的物品。')
    if '仓库已满且安全箱仍有物资' in reason:
        return ('仓库已满，安全箱仍有物品。程序已停止入仓。本局不计成功。'
                '程序不会出售物品腾出空位，也不会开始下一局。'
                '请先核对安全箱和仓库中的物品，再人工腾出仓库空位。')
    if '结算后仓库已满' in reason:
        return ('安全箱已空，但结算检查时仓库仍满。本局不计成功，也不会开始下一局。'
                '请核对仓库物品并人工腾出空位。')
    if '连续 3 局安全箱为空' in reason:
        return '连续 3 次空箱结算，未计成功。程序已完成返回流程，停止重开。'
    if '已完成仓库结算，停止自动重开' in reason:
        return ('失败局已完成结算，不再重开。本局不计成功。当前停在结算仓库。'
                '请查看日志和现场截图，检查失败原因，再决定是否重新启动任务。')
    if '自定义清理要同时选择类型和品质' in reason:
        return INCOMPLETE_SALE_HINT
    if reason == '人工结束':
        return '任务已按停止操作结束。请核对当前画面和携带物，再决定是否重新启动。'
    return '程序已停止，请检查现场。请先处理上述原因，再决定是否重新启动任务。'


def log_screenshot(name: str) -> None:
    """截图接口返回文件名；只展示确实保存的文件路径。"""
    try:
        if name:
            path = Path(debug_utils.get_debug_image_path(name))
            if path.is_file() and path.stat().st_size > 0:
                log.info('现场截图：%s', path.resolve())
                return
    except OSError:
        log.warning('无法核对现场截图文件。', exc_info=True)
    log.warning('本次未确认保存现场截图。请查看相关日志。')


def log_feedback() -> None:
    """从实际日志处理器读取路径，兼容自定义日志位置。"""
    log.info(FEEDBACK_HINT)
    paths = {str(handler.baseFilename) for handler in log.handlers if hasattr(handler, 'baseFilename')}
    if paths:
        log.info('当前日志：%s', '、'.join(sorted(paths)))
    else:
        log.info('日志默认在程序运行目录的 .log/；如已配置其他路径，请以该路径为准。')
    log.info('使用说明与问题反馈：%s', GUIDE_URL)
