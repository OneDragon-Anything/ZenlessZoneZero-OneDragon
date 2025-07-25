"""
小地图角度检测可视化工具

这个模块提供了对小地图角度检测算法的完整可视化功能，帮助理解算法的工作原理和调试问题。

主要功能：
1. 完整流程可视化：在一个大图中展示所有处理步骤
2. 分步骤可视化：每个步骤单独显示，便于详细分析
3. 扇形角度检测可视化：专门用于自动检测扇形角度的可视化
4. 方法比较：对比原始方法和扇形角度检测方法的结果
5. 测试数据生成：创建模拟的小地图用于测试
6. 结果保存：可以将可视化结果保存为图像文件

使用示例：
    # 基本角度检测可视化
    from one_dragon.utils.mini_map_angle_visualizer import MiniMapAngleVisualizer

    visualizer = MiniMapAngleVisualizer(save_dir='./output')
    angle, results = visualizer.visualize_full_process(minimap_image)

    # 扇形角度检测可视化
    sector_angle, results = visualizer.visualize_sector_angle_detection(minimap_image)

    # 从文件进行扇形角度检测
    from one_dragon.utils.mini_map_angle_visualizer import visualize_sector_angle_from_file
    sector_angle, results = visualize_sector_angle_from_file('minimap.png', save_dir='./output')

    # 比较两种检测方法
    from one_dragon.utils.mini_map_angle_visualizer import compare_detection_methods
    comparison = compare_detection_methods('minimap.png', save_dir='./output')

"""

import os
import platform
from typing import Optional, Tuple

import cv2
import matplotlib.pyplot as plt
import numpy as np
from cv2.typing import MatLike

from one_dragon.utils import debug_utils, os_utils
from one_dragon.utils.mini_map_angle_utils import calculate, calculate_sector_angle


def setup_chinese_font():
    """
    设置matplotlib支持中文字体
    """
    global CHINESE_FONT_AVAILABLE
    CHINESE_FONT_AVAILABLE = False

    try:
        import matplotlib.font_manager as fm

        # 根据操作系统选择合适的中文字体
        system = platform.system()

        if system == "Windows":
            # Windows系统常用中文字体
            fonts = ['SimHei', 'Microsoft YaHei', 'SimSun', 'KaiTi', 'FangSong']
        elif system == "Darwin":  # macOS
            # macOS系统中文字体
            fonts = ['PingFang SC', 'Hiragino Sans GB', 'STHeiti', 'Arial Unicode MS', 'Heiti SC']
        else:  # Linux
            # Linux系统中文字体
            fonts = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'Noto Sans CJK SC', 'Source Han Sans SC']

        # 尝试设置字体
        for font_name in fonts:
            try:
                # 更简单的字体检测方法
                plt.rcParams['font.sans-serif'] = [font_name] + plt.rcParams['font.sans-serif']
                plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

                # 测试中文字符是否能正常显示
                fig, ax = plt.subplots(figsize=(1, 1))
                ax.text(0.5, 0.5, '测试', fontsize=12)
                plt.close(fig)

                CHINESE_FONT_AVAILABLE = True
                print(f"已设置中文字体: {font_name}")
                break
            except Exception:
                continue

        if not CHINESE_FONT_AVAILABLE:
            # 如果没有找到合适的字体，使用默认设置
            plt.rcParams['font.family'] = ['sans-serif']
            plt.rcParams['axes.unicode_minus'] = False
            print("未找到合适的中文字体，将使用英文标题")

    except Exception as e:
        print(f"字体设置出现错误: {e}，将使用英文标题")
        CHINESE_FONT_AVAILABLE = False


def get_title(chinese_title: str, english_title: str) -> str:
    """
    根据字体支持情况返回合适的标题

    Args:
        chinese_title: 中文标题
        english_title: 英文标题

    Returns:
        合适的标题文本
    """
    return chinese_title if CHINESE_FONT_AVAILABLE else english_title


# 全局变量，标记是否支持中文字体
CHINESE_FONT_AVAILABLE = False

# 在模块加载时设置中文字体
setup_chinese_font()


def visualize_calculate(mini_map, results: dict):
    """
    创建可视化图表

    Args:
        results: 算法中间结果
    """
    # 创建大图，包含多个子图
    fig = plt.figure(figsize=(20, 16))
    fig.suptitle(get_title('小地图角度检测过程可视化', 'Minimap Angle Detection Process'),
                 fontsize=16, fontweight='bold')

    # 1. 原始图像和预处理
    ax1 = plt.subplot(3, 4, 1)
    plt.imshow(mini_map)
    plt.title(get_title('1. 原始小地图', '1. Original Minimap'))
    plt.axis('off')

    ax2 = plt.subplot(3, 4, 2)
    plt.imshow(results['original'], cmap='gray')
    plt.title(get_title('2. 视野', '2. View Mask'))
    plt.axis('off')

    # 2. 极坐标变换
    ax4 = plt.subplot(3, 4, 4)
    plt.imshow(results['polar_transform'], cmap='gray')
    plt.title(get_title('4. 极坐标变换', '4. Polar Transform'))
    plt.xlabel(get_title('角度', 'Angle'))
    plt.ylabel(get_title('半径', 'Radius'))

    # 3. 梯度检测
    ax5 = plt.subplot(3, 4, 5)
    gradient_display = np.clip(results['gradient'], -100, 100)  # 限制显示范围
    plt.imshow(gradient_display, cmap='RdBu')
    plt.title(get_title('5. 梯度检测', '5. Gradient Detection'))
    plt.xlabel(get_title('角度', 'Angle'))
    plt.ylabel(get_title('半径', 'Radius'))
    plt.colorbar()

    # 4. 边界检测结果
    ax6 = plt.subplot(3, 4, 6)
    x_axis = np.arange(len(results['left_boundary']))
    plt.plot(x_axis, results['left_boundary'], 'r-',
             label=get_title('左边界', 'Left Boundary'), linewidth=2)
    plt.plot(x_axis, results['right_boundary'], 'b-',
             label=get_title('右边界', 'Right Boundary'), linewidth=2)
    plt.title(get_title('6. 边界检测结果', '6. Boundary Detection'))
    plt.xlabel(get_title('角度索引', 'Angle Index'))
    plt.ylabel(get_title('强度', 'Intensity'))
    plt.legend()
    plt.grid(True, alpha=0.3)

    # 5. 卷积匹配结果
    ax7 = plt.subplot(3, 4, 7)
    conv_results = results['convolution_results']
    plt.imshow(conv_results, aspect='auto', cmap='hot')
    plt.title(get_title('7. 卷积匹配结果', '7. Convolution Results'))
    plt.xlabel(get_title('角度索引', 'Angle Index'))
    plt.ylabel(get_title('偏移量', 'Offset'))
    plt.colorbar()

    # 6. 最终结果
    if results['max_index'] is not None:
        ax8 = plt.subplot(3, 4, 8)
        final_result = results['final_result']
        x_axis = np.arange(len(final_result))
        plt.plot(x_axis, final_result, 'g-', linewidth=3)

        # 标记最大值点
        max_idx = results['max_index']
        detection_label = get_title(f'检测角度位置: {max_idx}', f'Detected Position: {max_idx}')
        plt.axvline(x=max_idx, color='red', linestyle='--', linewidth=2, label=detection_label)
        plt.scatter([max_idx], [final_result[max_idx]], color='red', s=100, zorder=5)

    view_angle = results['view_angle']
    if CHINESE_FONT_AVAILABLE:
        title_text = f'8. 最终结果\n角度: {view_angle}° (标准极坐标), 置信度: {results["confidence"]}'
    else:
        title_text = f'8. Final Result\nAngle: {view_angle}° (Standard Polar), Confidence: {results["confidence"]}'
    plt.title(title_text)
    plt.xlabel(get_title('角度索引', 'Angle Index'))
    plt.ylabel(get_title('响应强度', 'Response'))
    plt.legend()
    plt.grid(True, alpha=0.3)

    # 7. 在原图上标记检测到的角度
    ax9 = plt.subplot(3, 4, 9)
    original_with_angle = _draw_angle_on_minimap(mini_map, view_angle)
    plt.imshow(original_with_angle, cmap='gray')
    if CHINESE_FONT_AVAILABLE:
        title_text = f'9. 检测结果\n{view_angle}° (标准极坐标)'
    else:
        title_text = f'9. Detection Result\n{view_angle}° (Standard Polar)'
    plt.title(title_text)
    plt.axis('off')

    # 调整布局
    plt.tight_layout()

    # 显示图像
    plt.show()


def _draw_angle_on_minimap( minimap: MatLike, angle: float) -> MatLike:
    """
    在小地图上绘制检测到的角度方向

    Args:
        minimap: 原始小地图
        angle: 检测到的角度（标准极坐标系：0度为正右方向，逆时针增加）

    Returns:
        绘制了角度线的图像
    """
    result_img = minimap.copy()
    if angle is None:
        return result_img
    h, w = result_img.shape[:2]
    center = (w // 2, h // 2)

    # 计算角度线的终点
    # 注意：OpenCV的坐标系Y轴向下，所以需要取负号来正确显示逆时针方向
    radius = min(w, h) // 3
    angle_rad = np.radians(angle)
    end_x = int(center[0] + radius * np.cos(angle_rad))
    end_y = int(center[1] - radius * np.sin(angle_rad))  # Y轴取负号

    # 绘制角度线
    cv2.arrowedLine(result_img, center, (end_x, end_y), (0, 255, 0), 3, tipLength=0.3)

    # 绘制中心点
    cv2.circle(result_img, center, 5, (255, 0, 0), -1)

    # 添加角度文本和坐标系说明
    text = f'{angle:.1f}'
    cv2.putText(result_img, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    return result_img


def visualize_calculate_sector_angle(mini_map: MatLike, results: dict):
    """
    创建扇形角度检测的可视化图表

    Args:
        results: calculate_sector_angle的中间结果
    """
    # 创建大图，包含多个子图
    fig = plt.figure(figsize=(20, 16))
    fig.suptitle(get_title('小地图扇形角度检测过程可视化', 'Minimap Sector Angle Detection Process'),
                fontsize=16, fontweight='bold')

    # 1. 原始图像和预处理（与原方法相同）
    ax1 = plt.subplot(3, 4, 1)
    plt.imshow(mini_map, cmap='gray')
    plt.title(get_title('1. 原始小地图', '1. Original Minimap'))
    plt.axis('off')

    ax2 = plt.subplot(3, 4, 2)
    plt.imshow(results['original'], cmap='gray')
    plt.title(get_title('2. 视野', '2. View Mask'))
    plt.axis('off')

    # 2. 极坐标变换
    ax4 = plt.subplot(3, 4, 4)
    plt.imshow(results['polar_transform'], cmap='gray')
    plt.title(get_title('4. 极坐标变换', '4. Polar Transform'))
    plt.xlabel(get_title('角度', 'Angle'))
    plt.ylabel(get_title('半径', 'Radius'))

    # 3. 梯度检测
    ax5 = plt.subplot(3, 4, 5)
    gradient_display = np.clip(results['gradient'], -100, 100)  # 限制显示范围
    plt.imshow(gradient_display, cmap='RdBu')
    plt.title(get_title('5. 梯度检测', '5. Gradient Detection'))
    plt.xlabel(get_title('角度', 'Angle'))
    plt.ylabel(get_title('半径', 'Radius'))
    plt.colorbar()

    # 4. 原始边界检测结果
    ax6 = plt.subplot(3, 4, 6)
    plt.plot(results['left_boundary'], 'r-', label=get_title('左边界', 'Left Boundary'), linewidth=2)
    plt.plot(results['right_boundary'], 'b-', label=get_title('右边界', 'Right Boundary'), linewidth=2)
    plt.title(get_title('6. 原始边界检测', '6. Raw Boundary Detection'))
    plt.xlabel(get_title('角度索引', 'Angle Index'))
    plt.ylabel(get_title('响应强度', 'Response'))
    plt.legend()
    plt.grid(True, alpha=0.3)

    # 5. 平滑后的边界检测结果
    ax7 = plt.subplot(3, 4, 7)
    plt.plot(results['left_boundary_smoothed'], 'r-', label=get_title('左边界(平滑)', 'Left Boundary (Smoothed)'), linewidth=2)
    plt.plot(results['right_boundary_smoothed'], 'b-', label=get_title('右边界(平滑)', 'Right Boundary (Smoothed)'), linewidth=2)

    # 标记最大值位置
    plt.axvline(x=results['left_max_index'], color='red', linestyle='--', alpha=0.7,
               label=f"{get_title('左边界峰值', 'Left Peak')}: {results['left_angle']:.1f}°")
    plt.axvline(x=results['right_max_index'], color='blue', linestyle='--', alpha=0.7,
               label=f"{get_title('右边界峰值', 'Right Peak')}: {results['right_angle']:.1f}°")

    plt.title(get_title('7. 平滑边界检测', '7. Smoothed Boundary Detection'))
    plt.xlabel(get_title('角度索引', 'Angle Index'))
    plt.ylabel(get_title('响应强度', 'Response'))
    plt.legend()
    plt.grid(True, alpha=0.3)

    # 6. 扇形角度可视化
    ax8 = plt.subplot(3, 4, 8)
    # 创建角度圆盘可视化
    angles = np.linspace(0, 2*np.pi, 360)
    radius = 1

    # 绘制完整圆圈
    circle_x = radius * np.cos(angles)
    circle_y = radius * np.sin(angles)
    plt.plot(circle_x, circle_y, 'k-', alpha=0.3, linewidth=1)

    # 绘制扇形区域
    left_rad = np.radians(results['left_angle'])
    right_rad = np.radians(results['right_angle'])

    # 处理跨越0度的情况
    if abs(results['left_angle'] - results['right_angle']) > 180:
        # 跨越0度的扇形
        if results['left_angle'] > results['right_angle']:
            sector_angles = np.concatenate([
                np.linspace(left_rad, 2*np.pi, 50),
                np.linspace(0, right_rad, 50)
            ])
        else:
            sector_angles = np.concatenate([
                np.linspace(right_rad, 2*np.pi, 50),
                np.linspace(0, left_rad, 50)
            ])
    else:
        # 正常扇形
        start_angle = min(left_rad, right_rad)
        end_angle = max(left_rad, right_rad)
        sector_angles = np.linspace(start_angle, end_angle, 100)

    sector_x = radius * np.cos(sector_angles)
    sector_y = radius * np.sin(sector_angles)

    # 绘制扇形区域
    plt.fill(np.concatenate([[0], sector_x, [0]]),
            np.concatenate([[0], sector_y, [0]]),
            alpha=0.3, color='yellow', label=get_title('检测扇形', 'Detected Sector'))

    # 绘制边界线
    plt.plot([0, np.cos(left_rad)], [0, np.sin(left_rad)], 'r-', linewidth=3,
            label=f"{get_title('左边界', 'Left Boundary')}: {results['left_angle']:.1f}°")
    plt.plot([0, np.cos(right_rad)], [0, np.sin(right_rad)], 'b-', linewidth=3,
            label=f"{get_title('右边界', 'Right Boundary')}: {results['right_angle']:.1f}°")

    # 添加角度标注
    plt.text(0.7*np.cos(left_rad), 0.7*np.sin(left_rad), f"{results['left_angle']:.1f}°",
            fontsize=10, ha='center', va='center', color='red', fontweight='bold')
    plt.text(0.7*np.cos(right_rad), 0.7*np.sin(right_rad), f"{results['right_angle']:.1f}°",
            fontsize=10, ha='center', va='center', color='blue', fontweight='bold')

    plt.xlim(-1.2, 1.2)
    plt.ylim(-1.2, 1.2)
    plt.gca().set_aspect('equal')
    plt.title(f"{get_title('8. 扇形角度', '8. Sector Angle')}: {results['sector_angle']:.1f}°")
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1))
    plt.grid(True, alpha=0.3)

    # 7. 在原图上标记检测到的扇形
    ax9 = plt.subplot(3, 4, 9)
    original_with_sector = _draw_sector_on_minimap(mini_map,
                                                      results['left_angle'],
                                                      results['right_angle'])
    plt.imshow(original_with_sector, cmap='gray')
    if CHINESE_FONT_AVAILABLE:
        title_text = f'9. 检测结果\n扇形角度: {results["sector_angle"]:.1f}°\n置信度: {results["confidence"]:.3f}'
    else:
        title_text = f'9. Detection Result\nSector Angle: {results["sector_angle"]:.1f}°\nConfidence: {results["confidence"]:.3f}'
    plt.title(title_text)
    plt.axis('off')

    # 8. 检测质量评估
    ax10 = plt.subplot(3, 4, 10)
    confidence = results['confidence']

    # 创建置信度条形图
    colors = ['red' if confidence < 0.3 else 'orange' if confidence < 0.6 else 'green']
    bars = plt.bar(['Confidence'], [confidence], color=colors[0], alpha=0.7)
    plt.ylim(0, 1)
    plt.ylabel(get_title('置信度', 'Confidence'))
    plt.title(get_title('10. 检测质量', '10. Detection Quality'))

    # 添加置信度阈值线
    plt.axhline(y=0.3, color='orange', linestyle='--', alpha=0.7, label=get_title('可接受阈值', 'Acceptable Threshold'))
    plt.axhline(y=0.6, color='green', linestyle='--', alpha=0.7, label=get_title('良好阈值', 'Good Threshold'))

    # 添加数值标签
    plt.text(0, confidence + 0.05, f'{confidence:.3f}', ha='center', va='bottom', fontweight='bold')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # 调整布局
    plt.tight_layout()

    # 显示图像
    plt.show()

def _draw_sector_on_minimap(minimap: MatLike, left_angle: float, right_angle: float) -> MatLike:
    """
    在小地图上绘制检测到的扇形区域

    Args:
        minimap: 原始小地图
        left_angle: 左边界角度（标准极坐标系：0度为正右方向，逆时针增加）
        right_angle: 右边界角度（标准极坐标系：0度为正右方向，逆时针增加）

    Returns:
        绘制了扇形区域的图像
    """
    result_img = minimap.copy()
    h, w = result_img.shape[:2]
    center = (w // 2, h // 2)
    radius = min(w, h) // 3

    # 转换角度到OpenCV坐标系（Y轴向下）
    left_angle_cv = -left_angle
    right_angle_cv = -right_angle

    # 计算边界线的终点
    left_end_x = int(center[0] + radius * np.cos(np.radians(left_angle)))
    left_end_y = int(center[1] - radius * np.sin(np.radians(left_angle)))  # Y轴取负号

    right_end_x = int(center[0] + radius * np.cos(np.radians(right_angle)))
    right_end_y = int(center[1] - radius * np.sin(np.radians(right_angle)))  # Y轴取负号

    # 绘制扇形区域（使用椭圆弧）
    # 处理跨越0度的情况
    if abs(left_angle - right_angle) > 180:
        # 跨越0度的扇形，需要分两段绘制
        if left_angle > right_angle:
            # 绘制从left_angle到360度
            cv2.ellipse(result_img, center, (radius, radius), 0, left_angle_cv, 0, (100, 255, 100), 2)
            # 绘制从0度到right_angle
            cv2.ellipse(result_img, center, (radius, radius), 0, -360, right_angle_cv, (100, 255, 100), 2)
        else:
            # 绘制从right_angle到360度
            cv2.ellipse(result_img, center, (radius, radius), 0, right_angle_cv, 0, (100, 255, 100), 2)
            # 绘制从0度到left_angle
            cv2.ellipse(result_img, center, (radius, radius), 0, -360, left_angle_cv, (100, 255, 100), 2)
    else:
        # 正常扇形
        start_angle_cv = min(left_angle_cv, right_angle_cv)
        end_angle_cv = max(left_angle_cv, right_angle_cv)
        cv2.ellipse(result_img, center, (radius, radius), 0, start_angle_cv, end_angle_cv, (100, 255, 100), 2)

    # 绘制左边界线
    cv2.arrowedLine(result_img, center, (left_end_x, left_end_y), (0, 0, 255), 3, tipLength=0.3)

    # 绘制右边界线
    cv2.arrowedLine(result_img, center, (right_end_x, right_end_y), (255, 0, 0), 3, tipLength=0.3)

    # 绘制中心点
    cv2.circle(result_img, center, 5, (255, 255, 0), -1)

    # 添加角度文本
    cv2.putText(result_img, f'L:{left_angle:.1f}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    cv2.putText(result_img, f'R:{right_angle:.1f}', (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    cv2.putText(result_img, f'S:{abs(left_angle - right_angle):.1f}', (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 2)

    return result_img










