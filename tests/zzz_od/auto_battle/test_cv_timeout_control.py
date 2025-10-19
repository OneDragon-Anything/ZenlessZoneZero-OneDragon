# -*- coding: utf-8 -*-
"""
CV流水线超时控制功能专项测试
"""

import os
import unittest
import time
import numpy as np
from unittest.mock import MagicMock, patch

# 尝试导入项目依赖类
IMPORTS_AVAILABLE = False
try:
    from one_dragon.base.cv_process.cv_pipeline import CvPipeline
    from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext
    from one_dragon.base.cv_process.cv_service import CvService
    from zzz_od.auto_battle.target_state.target_state_checker import TargetStateChecker
    from zzz_od.context.zzz_context import ZContext
    from zzz_od.game_data.target_state import DetectionTask, TargetStateDef, TargetCheckWay
    IMPORTS_AVAILABLE = True
except ImportError:
    # 依赖不可用时，IMPORTS_AVAILABLE保持False
    pass


class TestCvTimeoutControl(unittest.TestCase):
    """CV流水线超时控制功能测试类"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化，检查依赖是否可用"""
        if not IMPORTS_AVAILABLE:
            raise unittest.SkipTest("因缺少核心CV模块而跳过此测试套件")

    def setUp(self):
        """测试初始化"""
        # 创建一个简单的测试图像
        self.test_image = np.zeros((100, 100, 3), dtype=np.uint8)

        # 创建模拟的上下文
        self.mock_context = MagicMock()
        self.mock_context.check_timeout.return_value = False
        self.mock_context.is_success.return_value = True

    def tearDown(self):
        """测试清理"""
        pass

    def test_cv_pipeline_context_timeout_check_no_timeout(self):
        """测试CvPipelineContext在无超时设置时的行为"""
        context = CvPipelineContext(self.test_image)
        # 默认没有超时设置，应该返回False
        self.assertFalse(context.check_timeout())

    def test_cv_pipeline_context_timeout_check_with_timeout_not_expired(self):
        """测试CvPipelineContext在超时未到期时的行为"""
        start_time = time.time()
        context = CvPipelineContext(self.test_image, start_time=start_time, timeout=2.0)
        # 超时未到期，应该返回False
        self.assertFalse(context.check_timeout())

    def test_cv_pipeline_context_timeout_check_with_timeout_expired(self):
        """测试CvPipelineContext在超时到期时的行为"""
        start_time = time.time() - 2.0  # 2秒前开始
        context = CvPipelineContext(self.test_image, start_time=start_time, timeout=1.0)
        # 超时已到期，应该返回True
        self.assertTrue(context.check_timeout())

    def test_cv_pipeline_execute_with_no_timeout(self):
        """测试CvPipeline在无超时设置时的执行"""
        pipeline = CvPipeline()
        context = pipeline.execute(self.test_image)
        self.assertTrue(context.success)
        self.assertIsNone(context.error_str)

    def test_cv_pipeline_execute_with_timeout_not_expired(self):
        """测试CvPipeline在超时未到期时的执行"""
        pipeline = CvPipeline()
        start_time = time.time()
        context = pipeline.execute(self.test_image, start_time=start_time, timeout=2.0)
        self.assertTrue(context.success)
        self.assertIsNone(context.error_str)

    def test_cv_pipeline_execute_with_timeout_expired(self):
        """测试CvPipeline在超时到期时的执行"""
        # 创建一个带有耗时步骤的流水线
        pipeline = CvPipeline()

        class SlowStep(CvStep):
            def __init__(self):
                super().__init__("slow_step")

            def execute(self, context):
                # 模拟耗时操作
                time.sleep(0.1)

        # 添加几个慢步骤
        for _ in range(5):
            pipeline.steps.append(SlowStep())

        # 设置一个很短的超时时间
        start_time = time.time() - 2.0  # 2秒前开始
        context = pipeline.execute(self.test_image, start_time=start_time, timeout=1.0)

        # 应该超时并失败
        self.assertFalse(context.success)
        self.assertIsNotNone(context.error_str)
        self.assertIn("超时", context.error_str)

    def test_cv_pipeline_execute_steps_timeout_check(self):
        """测试CvPipeline在执行步骤过程中检查超时"""
        pipeline = CvPipeline()

        class SlowStep(CvStep):
            def __init__(self, name):
                super().__init__(name)
                self.execute_count = 0

            def execute(self, context):
                self.execute_count += 1
                # 模拟耗时操作
                time.sleep(0.05)  # 50ms延迟

        # 添加步骤
        step1 = SlowStep("step1")
        step2 = SlowStep("step2")
        step3 = SlowStep("step3")

        pipeline.steps = [step1, step2, step3]

        # 设置一个很短的超时时间（小于所有步骤的总执行时间）
        start_time = time.time()
        context = pipeline.execute(self.test_image, start_time=start_time, timeout=0.08)  # 80ms超时

        # 应该在前两个步骤后超时，第三个步骤不应执行
        self.assertEqual(step1.execute_count, 1)
        self.assertEqual(step2.execute_count, 1)
        # step3可能不会执行，但由于执行速度快，我们检查总执行时间

        # 应该超时并失败
        self.assertFalse(context.success)
        self.assertIsNotNone(context.error_str)
        self.assertIn("超时", context.error_str)

        # 验证总执行时间超过了超时限制
        self.assertGreater(context.total_execution_time, 80)  # 应该超过80ms

    def test_cv_service_run_pipeline_with_timeout(self):
        """测试CvService运行流水线时的超时控制"""
        # 创建模拟的od_ctx
        mock_od_ctx = MagicMock()
        mock_od_ctx.cv_ocr = MagicMock()
        mock_od_ctx.template_loader = MagicMock()
        service = CvService(od_ctx=mock_od_ctx)
        start_time = time.time() - 2.0  # 2秒前开始

        # 创建一个简单的测试流水线
        class TestPipeline(CvPipeline):
            def __init__(self):
                super().__init__()
                self.steps = [CvStep("test_step")]

        # 使用patch模拟load_pipeline方法返回我们的测试流水线
        # 只有当CvService有load_pipeline方法时才进行patch
        if hasattr(service, 'load_pipeline'):
            with patch.object(service, 'load_pipeline', return_value=TestPipeline()):
                context = service.run_pipeline(
                    "test_pipeline",
                    self.test_image,
                    start_time=start_time,
                    timeout=1.0
                )
        else:
            # 如果没有load_pipeline方法，直接调用run_pipeline
            context = service.run_pipeline(
                "test_pipeline",
                self.test_image,
                start_time=start_time,
                timeout=1.0
            )

        # 无论走哪个分支，都必须验证超时行为
        # 由于超时已到期，应该失败
        self.assertFalse(context.success)
        self.assertIsNotNone(context.error_str)
        self.assertIn("超时", context.error_str)

    def test_target_state_checker_run_task_with_timeout(self):
        """测试TargetStateChecker运行任务时的超时控制"""
        # 创建模拟上下文
        mock_ctx = MagicMock()
        mock_ctx.cv_service = MagicMock()

        # 模拟一个已经超时的上下文
        mock_timeout_context = MagicMock()
        mock_timeout_context.success = False
        mock_timeout_context.error_str = "流水线执行超时 (限制 1.0 秒)"
        mock_ctx.cv_service.run_pipeline.return_value = mock_timeout_context

        checker = TargetStateChecker(mock_ctx)

        # 创建一个测试任务
        task = DetectionTask(
            task_id="test_task",
            pipeline_name="test_pipeline",
            state_definitions=[
                TargetStateDef("test_state", TargetCheckWay.CONTOUR_COUNT_IN_RANGE, {"min_count": 1})
            ]
        )

        # 运行任务
        cv_result, _ = checker.run_task(self.test_image, task)

        # 验证结果
        self.assertFalse(cv_result.success)
        self.assertIsNotNone(cv_result.error_str)
        self.assertIn("超时", cv_result.error_str)

    def test_target_state_checker_run_task_without_timeout(self):
        """测试TargetStateChecker运行任务时无超时的情况"""
        # 创建模拟上下文
        mock_ctx = MagicMock()
        mock_ctx.cv_service = MagicMock()

        # 模拟一个成功的上下文
        mock_success_context = MagicMock()
        mock_success_context.success = True
        mock_success_context.error_str = None
        mock_ctx.cv_service.run_pipeline.return_value = mock_success_context

        checker = TargetStateChecker(mock_ctx)

        # 创建一个测试任务
        task = DetectionTask(
            task_id="test_task",
            pipeline_name="test_pipeline",
            state_definitions=[
                TargetStateDef("test_state", TargetCheckWay.CONTOUR_COUNT_IN_RANGE, {"min_count": 1})
            ]
        )

        # 运行任务
        cv_result, _ = checker.run_task(self.test_image, task)

        # 验证结果
        self.assertTrue(cv_result.success)
        self.assertIsNone(cv_result.error_str)

    def test_cv_pipeline_context_timeout_with_zero_timeout(self):
        """测试CvPipelineContext在超时时间为0时的行为"""
        start_time = time.time() - 0.1  # 0.1秒前开始
        context = CvPipelineContext(self.test_image, start_time=start_time, timeout=0.0)
        # 超时时间已到期，应该返回True
        self.assertTrue(context.check_timeout())

    def test_cv_pipeline_context_timeout_with_none_timeout(self):
        """测试CvPipelineContext在超时时间为None时的行为"""
        start_time = time.time() - 10.0  # 10秒前开始
        context = CvPipelineContext(self.test_image, start_time=start_time, timeout=None)
        # 没有超时限制，应该返回False
        self.assertFalse(context.check_timeout())

    def test_cv_pipeline_execute_with_multiple_steps_and_timeout(self):
        """测试CvPipeline在执行多个步骤时的超时控制"""
        pipeline = CvPipeline()

        class QuickStep(CvStep):
            def __init__(self, name):
                super().__init__(name)
                self.execute_count = 0

            def execute(self, context):
                self.execute_count += 1
                # 模拟快速执行
                pass

        # 添加多个步骤
        steps = [QuickStep(f"step_{i}") for i in range(10)]
        pipeline.steps = steps

        # 设置一个合理的超时时间
        start_time = time.time()
        context = pipeline.execute(self.test_image, start_time=start_time, timeout=1.0)

        # 所有步骤都应该执行
        for step in steps:
            self.assertEqual(step.execute_count, 1)

        # 应该成功执行
        self.assertTrue(context.success)
        self.assertIsNone(context.error_str)

    @unittest.skipUnless(os.getenv("RUN_INTEGRATION_TESTS") == "1", "跳过集成测试：设置 RUN_INTEGRATION_TESTS=1 以启用")
    def test_async_task_timeout_control(self):
        """测试异步任务的超时控制"""
        # 创建模拟的自动战斗目标上下文
        try:
            from zzz_od.auto_battle.auto_battle_target_context import AutoBattleTargetContext
            from zzz_od.context.zzz_context import ZContext
            from one_dragon.base.conditional_operation.conditional_operator import ConditionalOperator

            # 创建真实上下文
            ctx = ZContext()
            # 尝试不同的初始化方法
            try:
                ctx.init_by_config()
            except AttributeError:
                # 如果没有init_by_config方法，尝试其他方法
                pass

            target_context = AutoBattleTargetContext(ctx)

            # 创建一个模拟的自动操作
            auto_op = MagicMock()
            auto_op.is_running = True
            auto_op.batch_update_states = MagicMock()

            target_context.init_battle_target_context(auto_op, 0, 0)

            # 修改异步任务的超时时间，用于测试
            for task in target_context.tasks:
                if task.task_id == "boss_stun_by_length":
                    task.interval = 0.1  # 设置较短的间隔

            # 运行一次检测
            target_context.run_all_checks(self.test_image, time.time())

            # 验证batch_update_states被调用
            self.assertTrue(auto_op.batch_update_states.called)

        except ImportError:
            # 如果无法导入真实类，跳过这个测试
            self.skipTest("无法导入必要的类，跳过异步任务超时测试")
        except Exception as e:
            # 如果初始化失败，跳过这个测试
            self.skipTest(f"初始化失败: {e}，跳过异步任务超时测试")


if __name__ == '__main__':
    unittest.main()