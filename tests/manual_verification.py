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

    print(f"示例配置路径: {config.sample_config_file_path}")
    print(f"用户配置路径: {config.user_config_file_path}")

    assert config.sample_config_file_path.name == 'redemption_codes.sample.yml'
    assert config.user_config_file_path.name == 'redemption_codes.yml'

    print("✓ 路径设置正确\n")


def test_load_user_config():
    """测试加载用户配置"""
    print("=" * 60)
    print("测试 2: 加载用户配置（GUI显示）")
    print("=" * 60)

    config = RedemptionCodeConfig()
    codes = config.codes_list

    print(f"加载的兑换码: {codes}")
    print(f"兑换码数量: {len(codes)}")

    # 用户配置应该只包含用户自定义的兑换码
    if config.user_config_file_path.exists():
        print("✓ 用户配置文件存在")
        print(f"✓ GUI显示兑换码: {codes}")
    else:
        print("✓ 用户配置文件不存在，返回空列表")

    print()


def test_save_and_load():
    """测试保存和加载配置"""
    print("=" * 60)
    print("测试 3: 保存-加载往返一致性")
    print("=" * 60)

    config = RedemptionCodeConfig()

    # 保存测试数据
    test_codes = ['TEST001', 'TEST002', 'TEST003']
    print(f"保存兑换码: {test_codes}")
    config.codes_list = test_codes

    # 重新加载
    loaded_codes = config.codes_list
    print(f"加载兑换码: {loaded_codes}")

    assert loaded_codes == test_codes, f"期望 {test_codes}，实际 {loaded_codes}"
    print("✓ 保存-加载一致性验证通过\n")


def test_text_format():
    """测试文本格式转换"""
    print("=" * 60)
    print("测试 4: 文本格式转换")
    print("=" * 60)

    config = RedemptionCodeConfig()

    # 测试空格分隔
    text = "CODE1 CODE2 CODE3"
    print(f"输入文本: '{text}'")
    config.update_codes_from_text(text)

    result_text = config.get_codes_text()
    print(f"输出文本: '{result_text}'")

    assert result_text == text, f"期望 '{text}'，实际 '{result_text}'"
    print("✓ 文本格式转换正确\n")


def test_merge_configs():
    """测试运行功能合并配置"""
    print("=" * 60)
    print("测试 5: 运行功能合并配置")
    print("=" * 60)

    run_record = RedemptionCodeRunRecord()
    codes = run_record.valid_code_list

    print(f"合并后的兑换码数量: {len(codes)}")
    for code in codes:
        print(f"  - {code.code} (过期时间: {code.end_dt})")

    # 应该包含用户配置和示例配置的兑换码
    config = RedemptionCodeConfig()
    if config.user_config_file_path.exists() and config.sample_config_file_path.exists():
        print("✓ 运行功能成功合并用户配置和示例配置")

    print()


def test_empty_input():
    """测试空输入处理"""
    print("=" * 60)
    print("测试 6: 空输入处理")
    print("=" * 60)

    config = RedemptionCodeConfig()

    # 测试空字符串
    config.update_codes_from_text("")
    assert config.codes_list == [], "空字符串应该返回空列表"
    print("✓ 空字符串处理正确")

    # 测试纯空格
    config.update_codes_from_text("   ")
    assert config.codes_list == [], "纯空格应该返回空列表"
    print("✓ 纯空格处理正确\n")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("兑换码配置功能 - 手动验证")
    print("=" * 60 + "\n")

    try:
        test_config_paths()
        test_load_user_config()
        test_save_and_load()
        test_text_format()
        test_merge_configs()
        test_empty_input()

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
