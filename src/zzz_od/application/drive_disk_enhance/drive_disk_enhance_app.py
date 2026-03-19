import time
import cv2,os
from typing import List, Dict, Any
import json
import subprocess
from pathlib import Path
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.application.drive_disk_enhance.drive_disk_enhance_const import APP_ID, APP_NAME
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.geometry.point import Point
from .ocr_worker import OcrWorker
from .drive_disk_parser import DriveDiskParser
from one_dragon.utils.cv2_utils import crop_image_only
from one_dragon.utils import yaml_utils
from one_dragon.utils import os_utils
from one_dragon.utils.str_utils import find_best_match_by_similarity

def sort_grids(all_disks: list[Point]) -> list[list[Point]]:
    """
    将所有点整理为二维网格
    
    Args:
        all_disks: 点列表
        
    Returns:
        二维网格，每个元素是一行点
    """
    if not all_disks:
        return []
    
    # 按 y 坐标排序
    sorted_by_y = sorted(all_disks, key=lambda d: d.y)
    
    rows = []
    current_row = [sorted_by_y[0]]
    y_tolerance = 20  # 行分组的容差，减小容差以更好地过滤异常数据
    
    for i in range(1, len(sorted_by_y)):
        disk = sorted_by_y[i]
        if abs(disk.y - current_row[0].y) <= y_tolerance:
            current_row.append(disk)
        else:
            # 对当前行按 x 坐标排序
            current_row.sort(key=lambda d: d.x)
            rows.append(current_row)
            current_row = [disk]
    
    # 处理最后一行
    if current_row:
        current_row.sort(key=lambda d: d.x)
        rows.append(current_row)
    
    # 过滤异常数据：非最后一行必须有4个点，最后一行可以有1-4个点
    filtered_rows = []
    for i, row in enumerate(rows):
        # 非最后一行必须有4个点
        if i < len(rows) - 1:
            if len(row) == 4:
                filtered_rows.append(row)
        # 最后一行可以有1-4个点
        else:
            if 1 <= len(row) <= 4:
                filtered_rows.append(row)
    
    return filtered_rows

class DriveDiskMapper:
    """驱动盘数据映射工具，将DriveDiskParser输出映射到zzz_drive-disk-rating格式"""
    
    # 属性名称映射表
    PROPERTY_NAME_MAP = {
        # 基础属性
        'hp': '小生命',
        'hp_': '生命值',
        'atk': '小攻击',
        'atk_': '攻击力',
        'def': '小防御',
        'def_': '防御力',
        # 战斗属性
        'crit_': '暴击率',
        'crit_dmg_': '暴击伤害',
        'pen': '穿透值',
        'pen_': '穿透率',
        'impact': '冲击力',
        'anomProf': '异常精通',
        'anomMas_': '异常掌控',
        'energyRegen_': '能量自动回复',
        # 属性伤害
        'fire_dmg_': '火属性伤害',
        'ice_dmg_': '冰属性伤害',
        'electric_dmg_': '电属性伤害',
        'ether_dmg_': '以太属性伤害',
        'physical_dmg_': '物理属性伤害'
    }
    
    @staticmethod
    def _clean_property_name(name: str) -> str:
        """清理属性名称，去除百分号"""
        return name.replace('%', '')
    
    @staticmethod
    def map_disc(parser_disc: Dict[str, Any]) -> Dict[str, Any]:
        """
        将DriveDiskParser输出的驱动盘数据映射到zzz_drive-disk-rating格式
        
        Args:
            parser_disc: DriveDiskParser解析的驱动盘数据
            
        Returns:
            映射后的驱动盘数据，符合zzz_drive-disk-rating格式
        """
        # 基础字段映射
        mapped_disc = {
            'position': int(parser_disc.get('slotKey', '1')),
            'name': parser_disc.get('setKey', 'Unknown'),
            'level': parser_disc.get('level', 0),
            'rarity': parser_disc.get('rarity', 'S'),
            'invalidProperty': 0,  # 需要根据角色权重配置计算
            'mainProperty': DriveDiskMapper._map_main_property(parser_disc),
            'subProperties': DriveDiskMapper._map_sub_properties(parser_disc.get('substats', []))
        }
        
        return mapped_disc
    
    @staticmethod
    def _map_main_property(parser_disc: Dict[str, Any]) -> Dict[str, str]:
        """映射主属性"""
        main_stat_key = parser_disc.get('mainStatKey', 'hp')
        main_property_name = DriveDiskMapper.PROPERTY_NAME_MAP.get(main_stat_key, main_stat_key)
        # 清理属性名称，去除百分号
        main_property_name = DriveDiskMapper._clean_property_name(main_property_name)
        
        # 估算主属性值（根据位置和等级）
        level = parser_disc.get('level', 0)
        slot_key = parser_disc.get('slotKey', '1')
        
        # 简单估算主属性值
        if slot_key in ['1', '2', '3']:
            # 固定值属性
            base_value = 100 + level * 10
            value = f"{base_value}"
        else:
            # 百分比属性
            base_value = 5 + level * 0.5
            value = f"{base_value}%"
        
        return {
            'name': main_property_name,
            'value': value
        }
    
    @staticmethod
    def _map_sub_properties(parser_substats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """映射副属性"""
        mapped_substats = []
        
        for substat in parser_substats:
            key = substat.get('key', '')
            upgrades = substat.get('upgrades', 1)
            
            sub_property_name = DriveDiskMapper.PROPERTY_NAME_MAP.get(key, key)
            # 清理属性名称，去除百分号
            sub_property_name = DriveDiskMapper._clean_property_name(sub_property_name)
            
            # 估算副属性值
            if key.endswith('_'):
                # 百分比属性
                base_value = 2 + (upgrades - 1) * 1.5
                value = f"{base_value}%"
            else:
                # 固定值属性
                base_value = 50 + (upgrades - 1) * 30
                value = f"{base_value}"
            
            mapped_substat = {
                'name': sub_property_name,
                'value': value,
                'level': upgrades,
                'valid': True,  # 默认有效，需要根据角色权重配置调整
                'add': upgrades - 1  # 额外升级次数
            }
            
            mapped_substats.append(mapped_substat)
        
        return mapped_substats
    
    @staticmethod
    def map_discs(parser_discs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """映射多个驱动盘"""
        return [DriveDiskMapper.map_disc(disc) for disc in parser_discs]
    
    @staticmethod
    def load_and_map(input_file: str, output_file: str) -> None:
        """
        从文件加载DriveDiskParser输出并映射到zzz_drive-disk-rating格式
        
        Args:
            input_file: 输入文件路径（scanned_discs.json）
            output_file: 输出文件路径
        """
        # 加载输入文件
        with open(input_file, 'r', encoding='utf-8') as f:
            parser_discs = json.load(f)
        
        # 映射数据
        mapped_discs = DriveDiskMapper.map_discs(parser_discs)
        
        # 保存输出文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(mapped_discs, f, indent=2, ensure_ascii=False)
        
        print(f"已成功映射 {len(mapped_discs)} 个驱动盘到 {output_file}")
    @staticmethod
    def map_from_json_string(json_string: str) -> List[Dict[str, Any]]:
        """
    直接从JSON字符串映射驱动盘数据
    
    Args:
        json_string: JSON格式的驱动盘数据字符串
        
    Returns:
        映射后的驱动盘数据列表
        """
        # 解析JSON字符串为Python对象
        parser_discs = json.loads(json_string)
        # 映射数据
        return DriveDiskMapper.map_discs(parser_discs)

def get_drive_disk_ratings(scanned_discs_input, character_name='露西亚'):
    """
    获取驱动盘评分结果
    
    Args:
        scanned_discs_input: 扫描的驱动盘数据文件路径或驱动盘对象或驱动盘对象列表
        character_name: 角色名称（默认：露西亚）
        
    Returns:
        评分结果列表
    """
    # Node.js 脚本路径（使用 Path 对象）
    script_path = Path(__file__).parent / 'process_scanned_discs.js'
    
    # 检查脚本是否存在
    if not script_path.exists():
        print(f"错误: 处理脚本不存在: {script_path}")
        print("请创建 process_scanned_discs.js 文件")
        return []
    
    # 处理输入参数
    temp_file = None
    try:
        # 检查输入类型
        if isinstance(scanned_discs_input, (dict, list)):
            # 输入是驱动盘对象或对象列表
            temp_file = Path(__file__).parent / 'temp_discs.json'
            # 确保是列表格式
            discs_data = [scanned_discs_input] if isinstance(scanned_discs_input, dict) else scanned_discs_input
            # 保存到临时文件
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(discs_data, f, ensure_ascii=False)
            scanned_discs_path = str(temp_file)
        else:
            # 输入是文件路径
            scanned_discs_path = scanned_discs_input
            # 检查文件是否存在
            if not Path(scanned_discs_path).exists():
                print(f"错误: 输入文件不存在: {scanned_discs_path}")
                return []
        
        # 构建命令
        cmd = [
            'node',
            str(script_path),
            str(scanned_discs_path),
            character_name
        ]
        
        # 执行命令，指定 UTF-8 编码
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',  # 关键修复：指定 UTF-8 编码
            cwd=str(script_path.parent)
        )
        
        if result.returncode != 0:
            print(f"错误: {result.stderr}")
            return []
        
        # 解析输出
        ratings = json.loads(result.stdout)
        return ratings
        
    except Exception as e:
        print(f"调用失败: {e}")
        return []
    finally:
        # 清理临时文件
        if temp_file and temp_file.exists():
            temp_file.unlink()

class DriveDiskEnhanceApp(ZApplication):

    def __init__(self, ctx: ZContext):
        """
        实现驱动盘的自动强化
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=APP_ID,
            op_name=APP_NAME,
        )
        ocr_worker = OcrWorker(ctx)
        ocr_worker.start()
        self.ocr_worker = ocr_worker
        self.parser = DriveDiskParser()
        self.reinforce_rect=self.ctx.screen_loader.get_area('代理人-驱动盘详细','强化').pc_rect
        self.add_stage_rect=self.ctx.screen_loader.get_area('代理人-驱动盘强化','阶段添加').pc_rect
        self.upgrade_rect=self.ctx.screen_loader.get_area('代理人-驱动盘强化','升级').pc_rect
        self.button_close_rect=self.ctx.screen_loader.get_area('代理人-驱动盘强化','按钮 - 关闭').pc_rect
        self.confirm_rect=self.ctx.screen_loader.get_area('代理人-驱动盘详细','材料返还-确认').pc_rect
        self.filter_rect = self.ctx.screen_loader.get_area('代理人-驱动盘详细','筛选').pc_rect
        self.reset_Rect = self.ctx.screen_loader.get_area('筛选','重置').pc_rect
        self.Grade_S_Rect = self.ctx.screen_loader.get_area('筛选','S').pc_rect
        self.suit_filter_Rect = self.ctx.screen_loader.get_area('筛选','套装选择').pc_rect
        self.confirm_filter_Rect = self.ctx.screen_loader.get_area('套装筛选','确认筛选').pc_rect
        self.drive_disk_list_Rect = self.ctx.screen_loader.get_area('代理人-驱动盘详细','驱动盘列表').pc_rect
        self.drive_disk_detail_Rect = self.ctx.screen_loader.get_area('代理人-驱动盘详细','驱动盘详细信息').pc_rect
        # 从上下文中获取驱动盘名称
        self.drive_disk_names = getattr(self.ctx, '_drive_disk_enhance_selections', [])
        print(f"从上下文获取驱动盘名称: {len(self.drive_disk_names)} 个")
        # 如果上下文中没有驱动盘名称，使用默认值
        if not self.drive_disk_names:
            print("上下文中没有驱动盘名称，使用默认值")
            # 默认驱动盘名称
            self.drive_disk_names = ['流光咏叹']
            print(f"使用默认驱动盘名称: {len(self.drive_disk_names)} 个")
        # 从上下文中读取用户选择的角色名称
        self.character_name = getattr(self.ctx, '_drive_disk_enhance_character', '叶瞬光')
        print(f"获取到前端角色: {self.character_name}")
        

    @operation_node(name='检测当前窗口是否为驱动盘详细页',is_start_node=True)
    def check_drive_disk_detail_page(self):
        """检测当前窗口是否为驱动盘详细页"""
        # 等待窗口激活
        import time
        time.sleep(0.5)
        
        # 截图并检测
        print("正在截图...")
        screen = self.screenshot()
        
        # 保存原始截图
        self.original_screenshot = screen
        
        print("正在识别当前画面...")
        # 使用check_and_update_current_screen综合判断当前画面
        current_screen = self.check_and_update_current_screen(
            screen=screen,
            screen_name_list=['代理人-驱动盘详细']
        )
        
        print(f"识别到的画面: {current_screen}")
        
        if current_screen == '代理人-驱动盘详细':
            print(f'检测到驱动盘详细页')
            return self.round_success(f'检测到驱动盘详细页')
        else:
            print(f'未检测到驱动盘详细页')
            return self.round_fail('未检测到驱动盘详细页')
    
    @node_from(from_name='检测当前窗口是否为驱动盘详细页')
    @operation_node(name='驱动盘方格处理',save_status=True)
    def process_drive_disk_grid(self):
        #初始化流水线和勾选分区的驱动盘方格位置
        grid_pipeline = self.ctx.cv_service.load_pipeline('驱动盘方格-代理人-驱动盘详细')
        suit_filter_pipeline = self.ctx.cv_service.load_pipeline('套装筛选')
        if grid_pipeline is None or suit_filter_pipeline is None:
                print('无法加载流水线配置')
                return self.round_fail('无法加载流水线配置')
        #遍历选定的驱动盘区域
        for i,disk_name in enumerate(self.drive_disk_names):
            #根据驱动盘名称判断是否需要处理并进行处理
            if disk_name:
                position = i + 1
                rect = self.ctx.screen_loader.get_area(f'代理人-驱动盘详细',f'{position}号位').pc_rect
                partition_center = Point((rect.x1 + rect.x2) / 2, (rect.y1 + rect.y2) / 2)# 将Rect对象转换为Point对象（使用中心点）
                self.ctx.controller.click(partition_center)
                time.sleep(1)
                print(f'点击了{position}号位')
                self.ctx.controller.click(self.filter_rect.center)
                time.sleep(0.3)
                self.ctx.controller.click(self.reset_Rect.center)
                time.sleep(0.3)
                self.ctx.controller.click(self.Grade_S_Rect.center)
                time.sleep(0.3)
                self.ctx.controller.click(self.suit_filter_Rect.center)
                time.sleep(0.3)
                target_text = [disk_name]
                found_target = False
                loop_count = 0
                max_loop_count = 10
                #筛选套装并回到驱动盘详细页
                while True:
                    loop_count += 1
                    if loop_count >= max_loop_count:
                        return self.round_fail(f'超过最大循环次数{max_loop_count}次数')
                    screen = self.screenshot()
                    result = suit_filter_pipeline.execute(screen,service=self.ctx.cv_service)
                    if result.success:
                        #print(f'识别到{len(result.ocr_result)}个文本项')
                        offset_x, offset_y = result.crop_offset
                        for ocr_text, match_list in result.ocr_result.items():
                            #print(f"\nocr识别文本: '{ocr_text};相对位置:{match_list[0].rect.center}'")
                            matched_text, score = find_best_match_by_similarity(ocr_text, target_text, threshold=0.69)
                            if matched_text:
                                #print(f"  模糊匹配到测试名称: {matched_text} (相似度: {score:.2f})")                               
                                if match_list:
                                    # 只点击第一个匹配项
                                    match = match_list[0]
                                    absolute_x1 = match.rect.x1 + offset_x
                                    absolute_y1 = match.rect.y1 + offset_y
                                    absolute_x2 = match.rect.x2 + offset_x
                                    absolute_y2 = match.rect.y2 + offset_y
                                    rect = Rect(absolute_x1, absolute_y1, absolute_x2, absolute_y2)
                                    #print(f'匹配的文本框的相对位置{match.rect.center}绝对位置:{rect.center}')
                                adjusted_center = rect.center - Point(0, 60)
                                #print(f'调整后的点击位置:{adjusted_center}')
                                self.ctx.controller.click(adjusted_center)
                                time.sleep(0.3)
                                self.ctx.controller.click(self.confirm_filter_Rect.center)
                                time.sleep(0.3)
                                self.ctx.controller.click(self.confirm_filter_Rect.center)#回到驱动盘详细页
                                time.sleep(1)
                                found_target = True
                                break
                        if found_target:
                            print("找到目标，退出循环")
                            break
                        print("未匹配到任何目标，执行滚动操作")
                        for i in range(3):
                            self.ctx.controller.scroll(1,Point(899,428))                             
                #return self.round_fail(f'强制结束,当前驱动盘名称为{disk_name}')                
                screen = self.screenshot()
                # 执行流水线处理
                #print('执行流水线处理...')
                context=grid_pipeline.execute(screen,service=self.ctx.cv_service)
                if not context.success:
                    #print(f'流水线执行失败: {context.error_str}')
                    return self.round_fail(f'流水线执行失败: {context.error_str}')
                # 获取处理结果
                filtered_contours = context.contours
                if not filtered_contours:
                    print('未检测到驱动盘方格')
                    return self.round_fail('未检测到驱动盘方格')
                print(f'检测到{position}号位的{len(filtered_contours)}个驱动盘方格')
                #更新all_grids,用于存储驱动盘方格中心点坐标的列表
                all_grids = []
                for contour in filtered_contours:
                   x, y, w, h = cv2.boundingRect(contour)
                   # 转换为绝对坐标
                   absolute_x = x + self.drive_disk_list_Rect.x1
                   absolute_y = y + self.drive_disk_list_Rect.y1
                   grid_center = Point(absolute_x + w / 2, absolute_y + h / 2)
                   all_grids.append(grid_center)
                #通过all_grids获取grid_rows
                grid_rows = sort_grids(all_grids)
                #print(f'当前驱动盘号位{position}的grid_rows={grid_rows}')
                #开始强化
                #初始化图片路径
                test_pictures_path=Path(__file__).parent.parent.parent.parent.parent / '.debug' / 'drive_disk_enhance_test_pictures'
                cropped_test_pictures_path=Path(__file__).parent.parent.parent.parent.parent / '.debug' / 'drive_disk_enhance_test_pictures' / 'cropped'
                # 创建目录（如果不存在）
                test_pictures_path.mkdir(parents=True, exist_ok=True)
                cropped_test_pictures_path.mkdir(parents=True, exist_ok=True)
                #初始化轮次
                loop_count = 0
                max_loops=50
                #开始进行比较分析 ,直到取得最优解或超过最大轮次
                while True:
                    loop_count += 1
                    if loop_count >= max_loops:
                        return self.round_fail(f'超过最大轮次{max_loops}次,自动结束')
                    #清空test_pictures_path
                    images = list(test_pictures_path.glob('*.png'))
                    for image_path in images:
                        os.remove(image_path)
                    images = list(cropped_test_pictures_path.glob('*.png'))
                    for image_path in images:
                        os.remove(image_path)
                    #截取所有驱动盘图片
                    for row_index,row in enumerate(grid_rows):
                        for col_index,point in enumerate(row):
                            self.ctx.controller.click(point)
                            print(f'当前分区的点击位置:{point}')
                            time.sleep(1)
                            screen = self.ctx.controller.get_screenshot()
                            cv2.imwrite(os.path.join(test_pictures_path, f'grid_{row_index}_{col_index}.png'), screen)
                    #读取所有捕获的图片,提交ocr任务
                    images = list(test_pictures_path.glob('*.png'))
                    for image_path in images:
                        image=cv2.imread(image_path)
                        if image is not None:
                            cropped_image = crop_image_only(image, self.drive_disk_detail_Rect)
                            cv2.imwrite(str(cropped_test_pictures_path / f'cropped_{image_path.stem}.png'), cropped_image)
                            self.ocr_worker.submit('disc',cropped_image,self.parser)
                        else:
                            print(f'无法读取图片 {image_path}')
                            return self.round_fail(f'无法读取图片 {image_path}')
                    #等待ocr完成任务
                    self.ocr_worker.wait_complete()
                    scanned_discs = self.ocr_worker.scanned_discs
                    mapped_discs=DriveDiskMapper.map_discs(scanned_discs)
                    #将获取的驱动盘信息写入json文件
                    with open(test_pictures_path / 'scanned_discs.json', 'w', encoding='utf-8') as f:
                        f.write(json.dumps(mapped_discs, ensure_ascii=False, indent=2))
                        #print("JSON数据已写入文件: scanned_discs.json")
                    self.ocr_worker.reset()#重置ocr_worker
                    ratings=get_drive_disk_ratings(mapped_discs,self.character_name)#按角色计算潜力值
                    if not ratings:
                        print('未检测到有效驱动盘')
                        return self.round_fail('未检测到有效驱动盘')
                    #更新潜力值列表
                    potentialScores=[]
                    for rating in ratings:
                        index=rating['index']
                        # 优化后评分（潜力值）
                        potential_score = rating['potentialScore']
                        potential_subPropertiesWeight = rating['potentialDetails']['subPropertiesWeight']
                        potential_mainPropertyWeight = rating['potentialDetails']['mainPropertyWeight']
                        potential_qualityWeight = rating['potentialDetails']['qualityWeight']
                        potential_levelWeight = rating['potentialDetails']['levelWeight']
                        potential_maxWeightSum = rating['potentialDetails']['maxWeightInfo']['maxWeightSum']
                        potential_validProperties=json.dumps(rating['potentialDetails']['validProperties'], ensure_ascii=False, indent=2)
                        potentialScores.append(potential_score)
                        #print(f'驱动盘索引值:{index},潜力值:{potential_score:.2f},潜力评分公式: (副属性权重:{potential_subPropertiesWeight:.2f}+主属性权重:{potential_mainPropertyWeight:.2f})*品质权重:{potential_qualityWeight:.2f}*等级权重:{potential_levelWeight:.2f}*每权重分值:{55/potential_maxWeightSum:.2f}\n有效属性:{potential_validProperties}')
                    max_index=potentialScores.index(max(potentialScores))
                    row=max_index//4 or 0
                    col=max_index%4 or 0
                    point=grid_rows[row][col]
                    self.ctx.controller.click(point)
                    screen = self.ctx.controller.get_screenshot()
                    cropped_image = crop_image_only(screen, self.drive_disk_detail_Rect)
                    self.ocr_worker.submit('disc',cropped_image,self.parser)
                    self.ocr_worker.wait_complete()
                    scanned_disc = self.ocr_worker.scanned_discs[0]
                    level=scanned_disc['level']
                    self.ocr_worker.reset()#重置ocr_worker
                    #print(f'当前最佳驱动盘等级{level}')
                    if level>=15:
                        print('当前已取得最优解,结束强化')
                        break                   
                    #执行强化操作
                    else:
                        self.ctx.controller.click(self.reinforce_rect.center)
                        time.sleep(0.5)
                        self.ctx.controller.click(self.add_stage_rect.center)
                        time.sleep(0.5)
                        self.ctx.controller.click(self.upgrade_rect.center)
                        time.sleep(0.5)
                        self.ctx.controller.click(self.button_close_rect.center)
                        time.sleep(1)
                        self.ctx.controller.click(self.confirm_rect.center)#初始化令鼠标点击材料返还确认按钮
        return self.round_success('驱动盘强化处理完成')
    
    # @node_from(from_name='驱动盘方格处理')
    # @operation_node(name='驱动盘强化')
    # def enhance_drive_disk(self):
    #     #获取all_grid_rows
    #     prev_node = self.node_status.get('驱动盘方格处理')
    #     all_grid_rows = prev_node.data.get('all_grid_rows', [])
    #     #获取驱动盘详细信息区域坐标
    #     crop_area=self.ctx.screen_loader.get_area('代理人-驱动盘详细','驱动盘详细信息')
    #     crop_rect=crop_area.pc_rect
    #     #初始化图片路径
    #     test_pictures_path=Path(__file__).parent.parent.parent.parent.parent / '.debug' / 'drive_disk_enhance_test_pictures'
    #     cropped_test_pictures_path=Path(__file__).parent.parent.parent.parent.parent / '.debug' / 'drive_disk_enhance_test_pictures' / 'cropped'
    #     # 创建目录（如果不存在）
    #     test_pictures_path.mkdir(parents=True, exist_ok=True)
    #     cropped_test_pictures_path.mkdir(parents=True, exist_ok=True)
    #     for partition_info in all_grid_rows:
    #         #初始化分区中心位置和网格信息
    #         center = partition_info['center']
    #         grid_rows = partition_info['grids']
    #         self.ctx.controller.click(center)
    #         print(f'驱动盘强化节点点击了{center}')
    #         time.sleep(1)
    #         #初始化轮次
    #         loop_count = 0
    #         max_loops=50
    #         while True:
    #             loop_count += 1
    #             if loop_count >= max_loops:
    #                 return self.round_fail(f'超过最大轮次{max_loops}次,自动结束')

    #             #清空test_pictures_path
    #             images = list(test_pictures_path.glob('*.png'))
    #             for image_path in images:
    #                 os.remove(image_path)
    #             images = list(cropped_test_pictures_path.glob('*.png'))
    #             for image_path in images:
    #                 os.remove(image_path)
    #             #截取所有驱动盘图片
    #             self.ctx.controller.click(self.confirm_rect.center)#初始化令鼠标点击确认按钮
    #             for row_index,row in enumerate(grid_rows):
    #                 for col_index,point in enumerate(row):
    #                     self.ctx.controller.click(point)
    #                     time.sleep(1)
    #                     screen = self.ctx.controller.get_screenshot()
    #                     cv2.imwrite(os.path.join(test_pictures_path, f'grid_{row_index}_{col_index}.png'), screen)
    #             #读取所有捕获的图片,提交ocr任务
    #             images = list(test_pictures_path.glob('*.png'))
    #             for image_path in images:
    #                 image=cv2.imread(image_path)
    #                 if image is not None:
    #                     cropped_image = crop_image_only(image, crop_rect)
    #                     cv2.imwrite(str(cropped_test_pictures_path / f'cropped_{image_path.stem}.png'), cropped_image)
    #                     self.ocr_worker.submit('disc',cropped_image,self.parser)
    #                 else:
    #                     print(f'无法读取图片 {image_path}')
    #             #等待ocr完成任务
    #             self.ocr_worker.wait_complete()
    #             scanned_discs = self.ocr_worker.scanned_discs
    #             mapped_discs=DriveDiskMapper.map_discs(scanned_discs)
    #             #将获取的驱动盘信息写入json文件
    #             with open(test_pictures_path / 'scanned_discs.json', 'w', encoding='utf-8') as f:
    #                 f.write(json.dumps(mapped_discs, ensure_ascii=False, indent=2))
    #                 print("JSON数据已写入文件: scanned_discs.json")
    #             self.ocr_worker.reset()#重置ocr_worker
    #             ratings=get_drive_disk_ratings(mapped_discs,self.character_name)#按角色计算潜力值
    #             if not ratings:
    #                 print('未检测到有效驱动盘')
    #                 return self.round_fail('未检测到有效驱动盘')
    #             #更新潜力值列表
    #             potentialScores=[]
    #             for rating in ratings:
    #                 index=rating['index']
    #                 # 优化后评分（潜力值）
    #                 potential_score = rating['potentialScore']
    #                 potential_subPropertiesWeight = rating['potentialDetails']['subPropertiesWeight']
    #                 potential_mainPropertyWeight = rating['potentialDetails']['mainPropertyWeight']
    #                 potential_qualityWeight = rating['potentialDetails']['qualityWeight']
    #                 potential_levelWeight = rating['potentialDetails']['levelWeight']
    #                 potential_maxWeightSum = rating['potentialDetails']['maxWeightInfo']['maxWeightSum']
    #                 potential_validProperties=json.dumps(rating['potentialDetails']['validProperties'], ensure_ascii=False, indent=2)
    #                 potentialScores.append(potential_score)
    #                 print(f'驱动盘索引值:{index},潜力值:{potential_score:.2f},潜力评分公式: (副属性权重:{potential_subPropertiesWeight:.2f}+主属性权重:{potential_mainPropertyWeight:.2f})*品质权重:{potential_qualityWeight:.2f}*等级权重:{potential_levelWeight:.2f}*每权重分值:{55/potential_maxWeightSum:.2f}\n有效属性:{potential_validProperties}')
    #             max_index=potentialScores.index(max(potentialScores))
    #             row=max_index//4 or 0
    #             col=max_index%4 or 0
    #             point=grid_rows[row][col]
    #             self.ctx.controller.click(point)
    #             screen = self.ctx.controller.get_screenshot()
    #             cropped_image = crop_image_only(screen, crop_rect)
    #             self.ocr_worker.submit('disc',cropped_image,self.parser)
    #             self.ocr_worker.wait_complete()
    #             scanned_disc = self.ocr_worker.scanned_discs[0]
    #             level=scanned_disc['level']
    #             self.ocr_worker.reset()#重置ocr_worker
    #             if level>=15:
    #                 print('当前已取得最优解,结束强化')
    #                 break
    #             #print(f'当前最佳驱动盘等级{level}')
    #             else:
    #                 self.ctx.controller.click(self.reinforce_rect.center)
    #                 time.sleep(0.5)
    #                 self.ctx.controller.click(self.add_stage_rect.center)
    #                 time.sleep(0.5)
    #                 self.ctx.controller.click(self.upgrade_rect.center)
    #                 time.sleep(0.5)
    #                 self.ctx.controller.click(self.button_close_rect.center)
    #                 time.sleep(1)
    #     return self.round_success('驱动盘扫描强化完成')
    # #def execute(self):
    # #     # 这里可以实现驱动盘强化的具体逻辑
    # #     return super().execute()

