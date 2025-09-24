"""
Qt颜色处理工具类
提供Qt GUI相关的颜色计算、转换等功能
"""
from PySide6.QtGui import QColor


class ColorUtils:
    """Qt颜色处理工具类"""
    
    @staticmethod
    def calculate_luminance(r: int, g: int, b: int) -> float:
        """
        计算颜色的相对亮度
        使用 ITU-R BT.709 标准的亮度计算公式
        
        Args:
            r: 红色分量 (0-255)
            g: 绿色分量 (0-255) 
            b: 蓝色分量 (0-255)
            
        Returns:
            float: 相对亮度值 (0-255)
        """
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    
    @staticmethod
    def get_text_color_for_background(r: int, g: int, b: int, threshold: float = 145) -> str:
        """
        根据背景色计算合适的文本颜色
        
        Args:
            r: 背景色红色分量 (0-255)
            g: 背景色绿色分量 (0-255)
            b: 背景色蓝色分量 (0-255)
            threshold: 亮度阈值，默认145
            
        Returns:
            str: "black" 或 "white"
        """
        luminance = ColorUtils.calculate_luminance(r, g, b)
        return "black" if luminance > threshold else "white"
    
    @staticmethod
    def is_light_color(r: int, g: int, b: int, threshold: float = 145) -> bool:
        """
        判断颜色是否为浅色
        
        Args:
            r: 红色分量 (0-255)
            g: 绿色分量 (0-255)
            b: 蓝色分量 (0-255)
            threshold: 亮度阈值，默认145
            
        Returns:
            bool: True表示浅色，False表示深色
        """
        luminance = ColorUtils.calculate_luminance(r, g, b)
        return luminance > threshold
    
    @staticmethod
    def extract_average_color_from_region(image, x0: int, y0: int, x1: int, y1: int, 
                                        sample_step: int = 64) -> tuple[int, int, int]:
        """
        从图片指定区域提取平均颜色
        
        Args:
            image: QImage对象
            x0, y0: 区域左上角坐标
            x1, y1: 区域右下角坐标
            sample_step: 采样步长，默认64
            
        Returns:
            Tuple[int, int, int]: RGB颜色值
        """
        r_sum = g_sum = b_sum = count = 0
        
        for y in range(y0, y1, max(1, (y1 - y0) // sample_step)):
            for x in range(x0, x1, max(1, (x1 - x0) // sample_step)):
                c = image.pixelColor(x, y)
                r_sum += c.red()
                g_sum += c.green()
                b_sum += c.blue()
                count += 1
        
        if count == 0:
            return 64, 158, 255  # 默认蓝色
        
        return int(r_sum / count), int(g_sum / count), int(b_sum / count)
    
    @staticmethod
    def enhance_color_vibrancy(r: int, g: int, b: int) -> tuple[int, int, int]:
        """
        增强颜色的鲜艳度
        
        Args:
            r, g, b: 原始RGB颜色值
            
        Returns:
            Tuple[int, int, int]: 增强后的RGB颜色值
        """
        base_color = QColor(r, g, b)
        h, s, v, a = base_color.getHsvF()
        
        if h < 0:  # 灰阶时 hue 可能为 -1
            h = 0.0
        
        # 增强饱和度和明度
        s = min(1.0, s * 2.0 + 0.25)
        v = min(1.0, v * 1.08 + 0.06)
        
        vivid = QColor.fromHsvF(h, s, v, 1.0)
        return vivid.red(), vivid.green(), vivid.blue()
    
    @staticmethod
    def brighten_if_too_dark(r: int, g: int, b: int, target_luminance: float = 160, 
                           max_iterations: int = 2) -> tuple[int, int, int]:
        """
        如果颜色太暗则适当提亮
        
        Args:
            r, g, b: 原始RGB颜色值
            target_luminance: 目标亮度值
            max_iterations: 最大调整次数
            
        Returns:
            Tuple[int, int, int]: 调整后的RGB颜色值
        """
        lr, lg, lb = r, g, b
        
        for _ in range(max_iterations):
            if ColorUtils.calculate_luminance(lr, lg, lb) >= target_luminance:
                break
                
            tmp = QColor(lr, lg, lb)
            th, ts, tv, ta = tmp.getHsvF()
            
            if th < 0:
                th = 0.0
            
            tv = min(1.0, tv + 0.10)  # 增加明度
            tmp2 = QColor.fromHsvF(th, ts, tv, 1.0)
            lr, lg, lb = tmp2.red(), tmp2.green(), tmp2.blue()
        
        return lr, lg, lb
    
    @staticmethod
    def limit_color_intensity(r: int, g: int, b: int, max_saturation: float = 0.7, 
                            max_value: float = 0.85, min_value: float = 0.3) -> tuple[int, int, int]:
        """
        限制颜色的饱和度和明度，避免过于鲜艳或过暗
        
        Args:
            r, g, b: 原始RGB颜色值
            max_saturation: 最大饱和度 (0-1)，默认0.7
            max_value: 最大明度 (0-1)，默认0.85
            min_value: 最小明度 (0-1)，默认0.3
            
        Returns:
            Tuple[int, int, int]: 限制后的RGB颜色值
        """
        color = QColor(r, g, b)
        h, s, v, a = color.getHsvF()
        
        if h < 0:  # 灰阶时 hue 可能为 -1
            h = 0.0
        
        # 限制饱和度，避免过于鲜艳
        s = min(max_saturation, s)
        
        # 限制明度范围，避免过亮或过暗
        v = max(min_value, min(max_value, v))
        
        limited_color = QColor.fromHsvF(h, s, v, 1.0)
        return limited_color.red(), limited_color.green(), limited_color.blue()
