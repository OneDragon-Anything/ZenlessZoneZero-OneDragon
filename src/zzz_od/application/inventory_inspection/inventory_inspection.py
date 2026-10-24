"""Opt-in independent OneDragon inspection, gated by native calibration.

Caller must be the inventory application already holding its native run lane.
Never start/login/update a game, initialize OCR, or change farming settings.
"""

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zzz_od.application.inventory_support.inventory_native_capture import (
    collect_page as collect_native_page,
)
from zzz_od.application.inventory_support.runtime import (
    import_support,
    inventory_root,
    valid_game_path,
)

DEFAULT_ROOT = inventory_root()
APP_ID = 'inventory_inspection'


def load_module(name: Any, path: Any) -> Any:
    return import_support(path)


_config = load_module(
    'onedragon_inventory_task_config', DEFAULT_ROOT / 'tools/inventory-task-config.py'
)
config_path = _config.config_path
NativeVersions = _config.NativeVersions


def prepare(root: Any, bridge: Any, navigation: Any, selected_ids: Any = None) -> Any:
    return _config.prepare(root, bridge, navigation, 'zzz', selected_ids=selected_ids)


def lane_matches(operation: Any, owner: Any) -> Any:
    ctx = operation.ctx
    run = ctx.run_context
    app_id = getattr(operation, 'app_id', None)
    return (
        app_id in (APP_ID, 'inventory_maintain')
        and run.is_context_running is True
        and (owner is not None)
        and (run.current_application is owner)
        and (run.current_app_id == app_id)
        and (run.current_instance_idx == ctx.current_instance_idx)
    )


def native_window_identity(
    controller: Any, process_api: Any, windows_api: Any, window_process_api: Any
) -> Any:
    handle = controller.game_win.get_hwnd()
    if not handle or not windows_api.IsWindow(handle) or windows_api.IsIconic(handle):
        raise RuntimeError('当前助手没有可交互的绝区零窗口')
    if windows_api.GetForegroundWindow() != handle:
        raise RuntimeError('绝区零失去前台，停止库存输入；不抢回焦点')
    pid = window_process_api.GetWindowThreadProcessId(handle)[1]
    process = process_api.Process(pid)
    return {
        'pid': pid,
        'path': process.exe(),
        'created': datetime.fromtimestamp(process.create_time(), UTC).isoformat(),
    }


def create_inventory_application(ctx: Any, root: Any = DEFAULT_ROOT) -> Any:
    """Native standalone application constructor, always opt-in.

    Do not use ZApplication's default OpenAndEnterGame operation. Disabling the
    game-window start node makes this inspection incapable of starting a game.
    A run record is not needed: every inspection must use new native evidence.
    """
    root = Path(root).resolve(strict=True)
    bridge = load_module(
        'onedragon_inventory_factory_bridge', root / 'tools/inventory-task-session.py'
    )
    navigation = load_module(
        'onedragon_inventory_factory_navigation',
        root / 'tools/inventory-native-navigation.py',
    )
    prepare(root, bridge, navigation)
    from one_dragon.base.operation.application_base import Application
    from one_dragon.base.operation.operation_node import operation_node

    return inventory_application_type(Application, operation_node)(ctx, root)


def inventory_application_type(Application: Any, operation_node: Any) -> Any:
    """Expose one real application class to native factory/description discovery.

    Building the class does not construct a context, read a plan or touch UI.
    Every instance validates its selected plan before the native base constructor.
    """

    class InventoryInspectionApplication(Application):
        """检查已标定的选定材料库存并报告缺口，不启动游戏或消耗道具。"""

        def __init__(self, ctx: Any, root: Any = DEFAULT_ROOT) -> None:
            root = Path(root).resolve(strict=True)
            bridge = load_module(
                'onedragon_inventory_factory_bridge',
                root / 'tools/inventory-task-session.py',
            )
            navigation = load_module(
                'onedragon_inventory_factory_navigation',
                root / 'tools/inventory-native-navigation.py',
            )
            prepare(root, bridge, navigation)
            Application.__init__(
                self,
                ctx=ctx,
                app_id=APP_ID,
                op_name='仓库检查',
                need_check_game_win=False,
                op_to_enter_game=None,
                node_max_retry_times=0,
                timeout_seconds=600,
            )
            self.run_record = None
            self.inventory_root = root

        @operation_node(
            name='检查并报告库存',
            is_start_node=True,
            node_max_retry_times=0,
            screenshot_before_round=False,
        )
        def inspect(self) -> Any:
            try:
                result = run_inventory_inspection(self, self.inventory_root)
                known = sum(row['status'] == 'confirmed' for row in result['materials'])
                unknown = len(result['materials']) - known
                return self.round_success(
                    status=f'选定库存已检查：核实{known}项，待核实{unknown}项',
                    data=result,
                )
            except Exception as exc:
                return self.round_fail(status=f'仓库检查未完成：{str(exc)[:240]}')

    return InventoryInspectionApplication


def run_inventory_inspection(
    operation: Any, root: Any = DEFAULT_ROOT, *, selected_ids: Any = None
) -> Any:
    root = Path(root).resolve(strict=True)
    bridge = load_module(
        'onedragon_inventory_bridge', root / 'tools/inventory-task-session.py'
    )
    navigation = load_module(
        'onedragon_inventory_navigation', root / 'tools/inventory-native-navigation.py'
    )
    folder = (
        root
        / 'audits'
        / datetime.now().strftime('%Y-%m-%d')
        / 'inventory'
        / datetime.now().strftime('onedragon-dispatch-%H%M%S-%f')
    )
    folder.mkdir(parents=True, exist_ok=False)
    attempt = {
        'schema': 'inventory-task-dispatch/v1',
        'game': 'zzz',
        'phase': 'preflight',
        'started_at': datetime.now(UTC).isoformat(),
        'status': 'started',
        'scope': 'inspection_only',
        'application_id': APP_ID,
        'implementation_file': str(Path(__file__).resolve()),
        'native_input_may_have_occurred': False,
        'farming_changed': False,
    }
    try:
        plan, selections, manifest = (
            prepare(root, bridge, navigation)
            if selected_ids is None
            else prepare(root, bridge, navigation, selected_ids)
        )
        attempt['application_id'] = getattr(operation, 'app_id', APP_ID)
        attempt['phase'] = 'native_process_and_versions'
        result = _run(
            operation, root, bridge, navigation, plan, selections, manifest, attempt
        )
        attempt.update(
            status='selected_inspection_finished',
            phase='finished',
            confirmed=sum(row['status'] == 'confirmed' for row in result['materials']),
        )
        return result
    except Exception as exc:
        attempt.update(
            status='failed_or_pending_no_success_report',
            error_type=type(exc).__name__,
            error=str(exc)[:2000],
        )
        raise
    finally:
        attempt['finished_at'] = datetime.now(UTC).isoformat()
        bridge.probe.atomic_json(folder / 'attempt.json', attempt)


def _run(
    op: Any,
    root: Any,
    bridge: Any,
    navigation: Any,
    plan: Any,
    selections: Any,
    manifest: Any,
    attempt: Any,
) -> Any:
    import psutil
    import win32gui
    import win32process

    from zzz_od.application.inventory_inspection.inventory_bag_port import NativeBagPort

    owner = op.ctx.run_context.current_application
    deadline = time.monotonic() + plan['budget_seconds']

    def identity() -> Any:
        return native_window_identity(op.ctx.controller, psutil, win32gui, win32process)

    if not lane_matches(op, owner):
        raise RuntimeError('绝区零库存检查不拥有当前应用执行权')
    expected = identity()
    executable = expected['path']
    if not valid_game_path('zzz', executable):
        raise RuntimeError('原生窗口不是目标游戏')
    if not bridge.same_identity(expected, dict(expected, path=executable)):
        raise RuntimeError('当前助手窗口不是已配置的绝区零安装')
    versions = NativeVersions(bridge.probe, executable, 'zzz')
    expected_versions = {
        'game_exe_sha256': manifest['game_exe_sha256'],
        'resource_fingerprints': manifest['resource_fingerprints'],
    }

    def control_guard() -> Any:
        if not lane_matches(op, owner):
            raise RuntimeError('库存检查已停止、暂停或应用执行权改变')
        if time.monotonic() >= deadline:
            raise TimeoutError('库存检查总预算已用尽')

    def guard() -> Any:
        control_guard()
        if (
            not bridge.same_identity(expected, identity())
            or versions() != expected_versions
        ):
            raise RuntimeError('绝区零窗口身份或资源版本改变，停止操作')
        control_guard()

    guard()
    selected_iter, events = (iter(selections), [])

    def event(name: Any, details: Any) -> Any:
        events.append({'at': datetime.now(UTC).isoformat(), 'event': name, **details})

    port = NativeBagPort(op, guard, event=event)

    def navigate(path: Any, cfg: Any) -> Any:
        guard()
        selected_path, material_id = next(selected_iter)
        if path != selected_path:
            raise RuntimeError('Selected page order changed')
        return navigation.find_selected_detail(
            port,
            cfg,
            manifest,
            guard,
            material_id=material_id,
            budget_seconds=min(60, max(1, int(deadline - time.monotonic()))),
            event=event,
        )

    def batch_scan(pages: Any, capture: Any) -> Any:
        guard()
        if [path for path, _ in pages] != [path for path, _ in selections]:
            raise RuntimeError('Batch page order changed')
        scanner = (
            navigation.scan_grouped_details
            if plan.get('scan_mode') == 'grouped'
            else navigation.scan_selected_details
        )
        return scanner(
            port,
            [
                (cfg, item_id)
                for (_, cfg), (_, item_id) in zip(pages, selections, strict=True)
            ],
            manifest,
            guard,
            capture,
            budget_seconds=max(1, int(deadline - time.monotonic())),
            event=event,
        )

    folder = (
        root
        / 'audits'
        / datetime.now().strftime('%Y-%m-%d')
        / 'inventory'
        / datetime.now().strftime('onedragon-task-%H%M%S-%f')
    )
    attempt['session_audit'] = str(folder)
    try:
        attempt.update(
            phase='native_navigation_and_capture', native_input_may_have_occurred=True
        )
        return bridge.inspect_session(
            'zzz',
            [file for file, _ in selections],
            expected,
            navigate=navigate,
            current_identity=identity,
            current_versions=versions,
            lane_available=lambda: lane_matches(op, owner),
            cancelled=lambda: not lane_matches(op, owner),
            audit_folder=folder,
            budget_seconds=plan['budget_seconds'],
            deadline_at=deadline,
            selected_material_ids=[item_id for _, item_id in selections],
            collector=lambda game, identity, path, seconds, *, selected_ids: (
                collect_native_page(
                    port,
                    game,
                    identity,
                    path,
                    seconds,
                    probe=bridge.probe,
                    folder=folder / datetime.now().strftime('capture-%H%M%S-%f'),
                    guard=guard,
                    selected_ids=selected_ids,
                )
            ),
            batch_scan=batch_scan
            if plan.get('scan_mode') in ('single_pass', 'grouped')
            else None,
        )
    finally:
        if folder.is_dir():
            bridge.probe.atomic_json(folder / 'navigation-events.json', events)
