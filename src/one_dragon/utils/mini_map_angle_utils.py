from functools import lru_cache

import cv2
import numpy as np
from cv2.typing import MatLike
from scipy import signal


@lru_cache
def generate_polar_remap_maps(
        d: int,
        angle_resolution: int = 360,
):
    """
    生成坐标映射表，用于将圆形区域“展开”成一个矩形（极坐标视图）。

    工作原理:
    想象一下将一个圆形的纸片从中心沿着一条半径剪开，然后将其完全展开成一个矩形。
    这个函数就是为这个过程生成所需的“操作指南”。
    它会创建两个映射表（mx, my），`cv2.remap` 函数会依据这两个表，将原始圆形图像上的像素点一一对应到新的矩形图像上。

    在新生成的矩形图像中：
    - 横轴 (x) 代表角度 (0° 到 360°)。
    - 纵轴 (y) 代表半径 (从圆心到边缘)。

    坐标系约定:
    - 0度角位于正右方。
    - 角度沿逆时针方向增加。

    Args:
        d: 原始正方形图像的边长。
        angle_resolution: 角度映射到横坐标的长度

    Returns:
        mx, my: 用于 cv2.remap 的x, y坐标映射表。
    """
    # 创建目标矩形图像的坐标网格。
    # i (行) 对应半径, j (列) 对应角度。
    i, j = np.meshgrid(np.arange(d), np.arange(angle_resolution), indexing='ij')

    # 将网格坐标 (i, j) 转换为极坐标 (radius, angle)。
    # 半径从 0 增长到 d/2。
    radius = i / 2
    # 当 j 从 0 变化到 angle_resolution 时，angles 从 0 变化到 2*pi (360度)
    angles = 2 * np.pi * j / angle_resolution

    # --- 核心转换 ---
    # 根据极坐标 (radius, angle) 计算出其在原始图像中的笛卡尔坐标 (mx, my)。
    # 这是标准的极坐标到笛卡尔坐标的转换公式。
    # mx = centerX + r * cos(theta)
    # my = centerY - r * sin(theta)  (注意：减号是为了让y轴向上为正，实现逆时针)
    center = d / 2
    mx = (center + radius * np.cos(angles)).astype(np.float32)
    my = (center - radius * np.sin(angles)).astype(np.float32)

    return mx, my


def create_angular_histogram_from_peaks(
    gradient_signal: np.ndarray,
    angular_resolution: int,
) -> np.ndarray:
    """
    从一个梯度信号中查找峰值，并将其投影到一维角度直方图上。

    这个函数的核心作用是，将一个（可能来自二维图像的）分散的峰值信号，
    通过类似“投票”的方式，统计并转换成一个一维的角度“置信度”数组。

    工作流程:
    1.  **查找峰值 (find_peaks)**: 在输入的一维梯度信号 `gradient_signal` 上找到
        所有符合 `peak_params` 条件的峰值点，并获取它们的索引。
    2.  **角度投影 (modulo %)**: 将每个峰值点的索引，通过对总角度分辨率
        `angular_resolution` 取模，计算出它对应的“角度”位置。
        如果原始信号来自一个被压平的2D图像，这一步等同于获取其原始的列号。
    3.  **统计票数 (bincount)**: `np.bincount` 负责统计每个“角度”位置上总共出现了
        多少个峰值点，最终生成一个代表“角度置信度”的一维直方图。

    Args:
        gradient_signal (np.ndarray): 输入的一维梯度信号 (通常是`gradient.ravel()`)。
        angular_resolution (int): 角度的总分辨率，即代表360度的像素总数。

    Returns:
        np.ndarray: 一个一维数组，其索引代表角度，值代表该角度上检测到的峰值数量。
    """
    # 1. 找到所有峰值在一维数组中的索引
    #    `signal.find_peaks` 返回一个元组，第一个元素是峰值的索引数组
    peak_indices = signal.find_peaks(
        gradient_signal,
        height=35,  # 峰值最小高度，过滤弱梯度
        wlen=angular_resolution,  # 峰值检测窗口长度
    )[0]

    # 2. 将一维索引转换为对应的角度位置
    angular_positions = peak_indices % angular_resolution

    # 3. 使用bincount将角度列表转换为“角度-数量”直方图
    #    minlength确保即使某些角度没有峰值，输出数组的长度也正确
    histogram = np.bincount(angular_positions, minlength=angular_resolution)

    return histogram


def peak_confidence(arr: np.ndarray) -> float:
    """
    评估最高峰的置信度，用于判断角度检测的可靠性
    通过比较最高峰和第二高峰的差异来评估检测结果的可信度

    Args:
        arr (np.ndarray): 一维数组，通常是角度响应强度数组

    Returns:
        float: 置信度值，范围0-1，越接近1表示检测越可靠
    """
    length = len(arr)  # 原始数组长度

    # 将数组重复3次连接，这样可以处理周期性数据（角度是周期性的）
    # 这样做可以避免在数组边界处丢失峰值
    extended_arr = np.concatenate((arr, arr, arr))
    peak_indices, properties = signal.find_peaks(
        extended_arr,
        height=0,
        prominence=5,
    )

    # 创建一个布尔掩码，筛选出位于原始数组范围内的峰值
    # [ 左侧的副本 | 我们关心的原始数据 | 右侧的副本 ]
    mask = (peak_indices >= length) & (peak_indices < 2 * length)
    valid_heights = properties['peak_heights'][mask]

    # 如果找到的峰值少于2个，则无法进行有意义的比较
    if valid_heights.size < 2:
        # 如果有1个峰值，它是绝对主导的，置信度为1
        # 如果有0个峰值，置信度为0 (修正了原版逻辑)
        return 1.0 if valid_heights.size == 1 else 0.0

    # 对峰值高度进行降序排序 np.partition 筛选前k个元素就位
    partitioned = np.partition(valid_heights, -2)
    highest: float = float(partitioned[-1])
    second: float = float(partitioned[-2])

    # 避免除以零的错误
    if highest == 0:
        return 0.0

    # 计算置信度：(最高峰 - 第二高峰) / 最高峰
    # 值越大表示最高峰越突出，检测结果越可靠
    confidence = (highest - second) / highest
    return confidence


def convolve(arr: np.ndarray, kernel: int = 3) -> np.ndarray:
    """
    使用 SciPy 高效实现带三角核的周期性卷积，用于平滑数组。

    Args:
        arr (np.ndarray): 输入的一维数组。
        kernel (int): 决定三角核宽度和锐度的参数。核的总宽度为 2*kernel - 1。

    Returns:
        np.ndarray: 卷积后的平滑数组。
    """
    # 1. 生成三角核 (Triangular Kernel)
    #    核的范围从 -kernel+1 到 kernel-1，总长度为 2*kernel - 1
    kernel_range = np.arange(-kernel + 1, kernel)

    #    根据公式 (kernel - abs(i)) / kernel 计算权重。
    triangle_kernel = (kernel - np.abs(kernel_range)) / float(kernel)

    # 2. 使用 SciPy 的 convolve 函数进行高效卷积
    #    mode='same' 确保输出与输入大小相同。
    #    method='fft' 利用快速傅里叶变换，对周期性数据处理得又快又好。
    return signal.convolve(arr, triangle_kernel, mode='same', method='fft')


def normalize_angle(angle: float) -> float:
    """将角度标准化到[0, 360)范围"""
    while angle >= 360:
        angle -= 360
    while angle < 0:
        angle += 360
    return angle

def calculate(
        view_mask: MatLike,
        scale: int = 1,
        angle_resolution: int = 360,
        radius_range: tuple[float, float] = (0.1, 0.6),
        view_angle: int = 90,
        debug_steps: bool = False,
) -> tuple[float, dict]:
    """
    计算小地图上角色的朝向角度，使用标准极坐标系：正右方为0度，逆时针方向增加
    需要小地图上有一个扇形的视野区域，返回的是右边界的角度

    算法原理：
    1. 小地图中心有一个扇形视野区域，表示角色的朝向
    2. 通过图像处理提取这个扇形的边界
    3. 将圆形坐标转换为矩形坐标，便于处理
    4. 使用梯度检测找到扇形的左右边界
    5. 通过卷积和峰值检测确定最终角度

    Args:
        view_mask: 小地图图像，处理为视野遮罩的mask，应为正方形
        scale: 图像的缩放因子，放大可用于提高检测精度
        angle_resolution: 角度分辨率，中心圆形展开时的宽度，值越小计算越快，误差大
        radius_range: 计算采用的半径范围，避免中心点和边缘的干扰
        view_angle: 视野角度 即扇形的角度 通常是90度
        debug_steps: 是否保存调试步骤结果

    Returns:
        tuple: (角度, 步骤结果字典)
            - 角度: float, 角色朝向角度（度），标准极坐标系：0度为正右方向，逆时针增加
            - 步骤结果字典: dict, 包含每个处理步骤的中间结果
                - 'original': 原始小地图图像
                - 'yuv_v_channel': YUV色彩空间的V通道
                - 'inverted': 反转亮度后的图像
                - 'polar_transform': 极坐标变换后的图像
                - 'gradient': 梯度检测结果
                - 'left_boundary': 左边界检测结果
                - 'right_boundary': 右边界检测结果
                - 'convolution_results': 卷积匹配结果
                - 'final_result': 最终响应结果
                - 'confidence': 检测置信度
                - 'view_angle': 检测到的角度
                - 'max_index': 最大响应位置索引
    """
    d = view_mask.shape[0]  # 获取图像尺寸 即小地图的直径

    # 第二步：坐标变换，将圆形区域展开为矩形
    # 获取极坐标到直角坐标的映射矩阵
    m1, m2 = generate_polar_remap_maps(d, angle_resolution=angle_resolution)

    # 使用remap将圆形图像按角度展开为矩形
    # 展开后：行代表半径，列代表角度 remap.shape=(d, angle_resolution)
    remap = cv2.remap(view_mask, m1, m2, cv2.INTER_LINEAR)
    # 只取中间部分，避免中心点和边缘的干扰
    remap = remap[int(d * radius_range[0]):int(d * radius_range[1])].astype(np.float32)
    # 根据scale参数放大图像，提高角度检测精度
    remap = cv2.resize(remap, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)

    # 第三步：梯度检测，找到视野扇形的边界
    # 使用Scharr算子计算x方向（角度方向）的梯度 扇形边界处会有强烈的梯度变化
    gradient = cv2.Scharr(remap, cv2.CV_32F, 1, 0)

    # 第四步：峰值检测，找到扇形的左右边界
    # 检测正梯度峰值（左边界）和负梯度峰值（右边界） 按角度统计峰值出现次数
    # ravel() 将2D梯度图展平为1D数组 第1行第2行第3行那样拼接起来
    l_hist = create_angular_histogram_from_peaks(
        gradient_signal=gradient.ravel(),
        angular_resolution=angle_resolution * scale
    )
    # 注意：通过给gradient取反，找到负梯度峰值
    r_hist = create_angular_histogram_from_peaks(
        gradient_signal=-gradient.ravel(),
        angular_resolution=angle_resolution * scale
    )

    # 分离左右边界：只保留左边界强于右边界的位置作为左边界，反之亦然
    # 这样可以避免同一位置既是左边界又是右边界的情况
    l, r = np.maximum(l_hist - r_hist, 0), np.maximum(r_hist - l_hist, 0)

    # 第五步：卷积匹配，寻找最佳的扇形角度
    # 1. 创建用于平滑 r 信号的三角核
    kernel_width = 2 * scale
    triangle_ker_size = 3 * kernel_width
    r_convolved = convolve(r, triangle_ker_size)

    # 3. 在循环中，仅对预先计算好的卷积结果进行高效移位
    conv0 = []
    view_angle_width = int(angle_resolution * view_angle * scale / 360)
    for offset in range(-kernel_width + 1, kernel_width):
        # 使用 np.roll 对预卷积的数组进行高效的周期性移位
        blurred_r_template = np.roll(r_convolved, shift=-view_angle_width + offset)
        # 左边界信号*模糊的右边界信号 如果是左右边界匹配，则乘积结果会很大 方便后续评估
        conv0.append(l * blurred_r_template)

    # 第六步：结果处理和置信度评估
    # 确保所有值都大于等于1，避免后续计算出现问题
    conv0 = np.maximum(conv0, 1)
    # 取所有偏移结果的最大值，得到最强的响应
    maximum = np.max(conv0, axis=0)
    # 计算检测置信度
    rotation_confidence = round(peak_confidence(maximum), 3)

    if rotation_confidence > 0:
        result = maximum
    else:
        # 进行额外的平滑处理以减少噪声
        average = np.mean(conv0, axis=0)  # 计算平均值
        minimum = np.min(conv0, axis=0)   # 计算最小值

        # 组合最大值、平均值和最小值，然后进行卷积平滑
        # 这种组合可以增强真实信号，抑制噪声
        result = convolve(maximum * average * minimum, 2 * scale)
        rotation_confidence = round(peak_confidence(maximum), 3)

    # 第七步：将匹配点转换为角度
    if rotation_confidence <= 0:
        # 放弃当前结果
        max_index = None
        degree = None
    else:
        # 找到响应最强的位置（角度索引）
        max_index = int(np.argmax(result))
        # 将索引转换为标准极坐标角度：[0,360)
        # 由右边界计算中心的坐标
        degree = (max_index * 360.0 / (angle_resolution * scale)) + (view_angle / 2.0)
        # 确保角度在[0, 360)范围内
        degree = normalize_angle(degree)

    # 存储每个步骤的结果
    if debug_steps:
        steps = {
            'original': view_mask,
            'polar_transform': remap,
            'gradient': gradient,
            'left_boundary': l,
            'right_boundary': r,
            'convolution_results': np.array(conv0),
            'final_result': result,
            'confidence': rotation_confidence,
            'max_index': max_index,
            'view_angle': degree
        }
    else:
        steps = None

    return degree, steps


def calculate_sector_angle(
        view_mask: MatLike,
        scale: int = 1,
        angle_resolution: int = 360,
        radius_range: tuple[float, float] = (0.1, 0.6),
        debug_steps: bool = False,
) -> tuple[float, dict]:
    """
    自动计算小地图上扇形视野的角度，使用与calculate相同的算法

    这个方法不需要预设视野角度，而是通过分析梯度边界来自动检测扇形的实际角度。
    适用于未知视野角度的游戏或需要动态检测扇形大小的场景。

    算法原理：
    1. 使用与calculate相同的图像预处理和极坐标变换
    2. 通过梯度检测找到扇形的左右边界
    3. 分别找到左右边界的最强响应位置
    4. 计算两个边界之间的角度差作为扇形角度
    5. 处理跨越0°/360°的特殊情况

    Args:
        view_mask: 小地图图像，应为正方形
        scale: 图像的缩放因子，放大可用于提高检测精度
        angle_resolution: 角度分辨率，中心圆形展开时的宽度，值越小计算越快，误差大
        radius_range: 计算采用的半径范围，避免中心点和边缘的干扰
        debug_steps: 是否保存调试步骤结果

    Returns:
        tuple: (扇形角度, 步骤结果字典)
            - 扇形角度: float, 检测到的扇形角度（度）
            - 步骤结果字典: dict, 包含每个处理步骤的中间结果
                - 'original': 原始小地图图像
                - 'yuv_v_channel': YUV色彩空间的V通道
                - 'inverted': 反转亮度后的图像
                - 'polar_transform': 极坐标变换后的图像
                - 'gradient': 梯度检测结果
                - 'left_boundary': 左边界检测结果
                - 'right_boundary': 右边界检测结果
                - 'left_boundary_smoothed': 平滑后的左边界
                - 'right_boundary_smoothed': 平滑后的右边界
                - 'left_angle': 左边界角度
                - 'right_angle': 右边界角度
                - 'sector_angle': 扇形角度
                - 'confidence': 检测置信度
                - 'left_max_index': 左边界最大响应索引
                - 'right_max_index': 右边界最大响应索引
    """
    d = view_mask.shape[0]  # 获取图像尺寸 即小地图的直径

    # 第二步：坐标变换，将圆形区域展开为矩形（与calculate方法相同）
    # 获取极坐标到直角坐标的映射矩阵
    m1, m2 = generate_polar_remap_maps(d, angle_resolution=angle_resolution)

    # 使用remap将圆形图像按角度展开为矩形
    # 展开后：行代表半径，列代表角度 remap.shape=(d, angle_resolution)
    remap = cv2.remap(view_mask, m1, m2, cv2.INTER_LINEAR)
    # 只取中间部分，避免中心点和边缘的干扰
    remap = remap[int(d * radius_range[0]):int(d * radius_range[1])].astype(np.float32)
    # 根据scale参数放大图像，提高角度检测精度
    remap = cv2.resize(remap, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)

    # 第三步：梯度检测，找到视野扇形的边界（与calculate方法相同）
    # 使用Scharr算子计算x方向（角度方向）的梯度 扇形边界处会有强烈的梯度变化
    gradient = cv2.Scharr(remap, cv2.CV_32F, 1, 0)

    # 第四步：峰值检测，找到扇形的左右边界（与calculate方法相同）
    # 检测正梯度峰值（左边界）和负梯度峰值（右边界） 按角度统计峰值出现次数
    # ravel() 将2D梯度图展平为1D数组 第1行第2行第3行那样拼接起来
    l_hist = create_angular_histogram_from_peaks(
        gradient_signal=gradient.ravel(),
        angular_resolution=angle_resolution * scale
    )
    # 注意：通过给gradient取反，找到负梯度峰值
    r_hist = create_angular_histogram_from_peaks(
        gradient_signal=-gradient.ravel(),
        angular_resolution=angle_resolution * scale
    )

    # 分离左右边界：只保留左边界强于右边界的位置作为左边界，反之亦然
    # 这样可以避免同一位置既是左边界又是右边界的情况
    l, r = np.maximum(l_hist - r_hist, 0), np.maximum(r_hist - l_hist, 0)

    # 第五步：边界平滑和角度计算
    # 对左右边界进行平滑处理，提高检测稳定性
    kernel_width = 2 * scale
    triangle_ker_size = 3 * kernel_width

    l_smoothed = convolve(l, triangle_ker_size)
    r_smoothed = convolve(r, triangle_ker_size)

    # 第六步：分别计算左右边界角度
    # 找到左边界的最强响应位置
    left_max_index = int(np.argmax(l_smoothed))
    left_angle = (left_max_index * 360.0 / (angle_resolution * scale))

    # 找到右边界的最强响应位置
    right_max_index = int(np.argmax(r_smoothed))
    right_angle = (right_max_index * 360.0 / (angle_resolution * scale))

    # 第七步：计算扇形角度，处理跨越0°/360°的情况
    left_angle = normalize_angle(left_angle)
    right_angle = normalize_angle(right_angle)

    # 计算扇形角度，考虑跨越0°的情况
    if abs(left_angle - right_angle) <= 180:
        # 正常情况，不跨越0°
        sector_angle = abs(left_angle - right_angle)
    else:
        # 跨越0°的情况
        sector_angle = 360 - abs(left_angle - right_angle)

    # 第八步：计算检测置信度
    # 使用左右边界的平均置信度
    left_confidence = peak_confidence(l_smoothed)
    right_confidence = peak_confidence(r_smoothed)
    overall_confidence = round((left_confidence + right_confidence) / 2, 3)

    # 存储每个步骤的结果
    if debug_steps:
        steps = {
            'original': view_mask,
            'polar_transform': remap,
            'gradient': gradient,
            'left_boundary': l,
            'right_boundary': r,
            'left_boundary_smoothed': l_smoothed,
            'right_boundary_smoothed': r_smoothed,
            'left_angle': left_angle,
            'right_angle': right_angle,
            'sector_angle': sector_angle,
            'confidence': overall_confidence,
            'left_max_index': left_max_index,
            'right_max_index': right_max_index,
        }
    else:
        steps = None

    return sector_angle, steps
