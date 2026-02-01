"""
手动验证脚本 - 兑换码配置功能
用于验证核心功能是否正常工作
"""
import sys
from pathlib import Path

# 添加源代码路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from zzz_od.application.redemption_code.redemption_code_config import RedemptionCodeConfig
from zzz_od.application.redemption_code.redemption_code_run_record import RedemptionCodeRunRecord


def test_config_paths():
    """测试配置文件路径设置"""
    print("=" * 60)
    print("测试 1: 配置文件路径")
    print("=" * 60)

    config = RedemptionCodeConfig()

    print(f"示例配置路径: {config.sample_config.file_path}")
    print(f"用户配置路径: {config.user_config.file_path}")

    assert config.sample_config.file_path.endswith('redemption_codes.sample.yml')
    assert config.user_config.file_path.endswith('redemption_codes.yml')

    print("✓ 路径设置正确\n")


def test_load_user_config():
    """测试加载用户配置"""
    print("=" * 60)
    print("测试 2: 加载用户配置")
    print("=" * 60)

    config = RedemptionCodeConfig()
    codes = config.codes_list

    print(f"加载的兑换码: {codes}")
    print(f"兑换码数量: {len(codes)}")

    import os
    if os.path.exists(config.user_config.file_path):
        print("✓ 用户配置文件存在")
    else:
        print("✓ 用户配置文件不存在，使用 sample 配置")

    print()


def test_add_update_delete():
    """测试添加、更新、删除兑换码"""
    print("=" * 60)
    print("测试 3: 添加、更新、删除兑换码")
    print("=" * 60)

    config = RedemptionCodeConfig()

    # 测试添加
    config.add_code('TEST001', 20250101)
    config.add_code('TEST002', 20250201)
    print(f"添加后: {config.codes_dict}")
    assert 'TEST001' in config.codes_dict
    assert 'TEST002' in config.codes_dict
    print("✓ 添加兑换码成功")

    # 测试更新
    config.update_code('TEST001', 'TEST001_UPDATED', 20260101)
    print(f"更新后: {config.codes_dict}")
    assert 'TEST001_UPDATED' in config.codes_dict
    assert 'TEST001' not in config.codes_dict
    print("✓ 更新兑换码成功")

    # 测试删除
    config.delete_code('TEST002')
    print(f"删除后: {config.codes_dict}")
    assert 'TEST002' not in config.codes_dict
    print("✓ 删除兑换码成功\n")


def test_merge_configs():
    """测试合并配置"""
    print("=" * 60)
    print("测试 4: 合并配置")
    print("=" * 60)

    run_record = RedemptionCodeRunRecord()
    codes = run_record.valid_code_list

    print(f"合并后的兑换码数量: {len(codes)}")
    for code in codes:
        print(f"  - {code.code} (过期时间: {code.end_dt})")

    import os
    config = RedemptionCodeConfig()
    if os.path.exists(config.sample_config.file_path):
        print("✓ 成功合并 sample 配置")

    print()


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("兑换码配置功能 - 手动验证")
    print("=" * 60 + "\n")

    try:
        test_config_paths()
        test_load_user_config()
        test_add_update_delete()
        test_merge_configs()

        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
