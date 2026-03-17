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
    y_tolerance = 50  # 行分组的容差
    
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
    
    return rows

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

        # 获取前端勾选状态
        self.checkbox_states = getattr(self.ctx, '_drive_disk_enhance_states', [True, True, True, True, True, True])
        print(f"获取到前端勾选状态: {self.checkbox_states}")
        # 从上下文中读取用户选择的角色名称
        self.character_name = getattr(self.ctx, '_drive_disk_enhance_character', '叶瞬光')
        print(f"使用角色: {self.character_name}")
        

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
            return self.round_success('检测到驱动盘详细页')
        else:
            print(f'未检测到驱动盘详细页')
            return self.round_fail('未检测到驱动盘详细页')
    
    @node_from(from_name='检测当前窗口是否为驱动盘详细页')
    @operation_node(name='驱动盘方格处理',save_status=True)
    def process_drive_disk_grid(self):
        #初始化流水线和勾选分区的驱动盘方格位置
        pipeline = self.ctx.cv_service.load_pipeline('驱动盘方格-代理人-驱动盘详细')
        if pipeline is None:
                print('无法加载流水线配置')
                return self.round_fail('无法加载流水线配置')
        print(f'流水线加载成功，包含{len(pipeline.steps)}个步骤')
        all_grid_rows=[]
        for i,checked in enumerate(self.checkbox_states):
            #获取勾选位置
            if checked:
                position = i + 1
                rect = self.ctx.screen_loader.get_area(f'代理人-驱动盘详细',f'{position}号位').pc_rect
                partition_center = Point((rect.x1 + rect.x2) / 2, (rect.y1 + rect.y2) / 2)# 将Rect对象转换为Point对象（使用中心点）
                self.ctx.controller.click(partition_center)
                time.sleep(1)
                print(f'点击了{position}号位')
                screen = self.screenshot()
                # 执行流水线处理
                print('执行流水线处理...')
                context=pipeline.execute(screen,service=self.ctx.cv_service)
                if not context.success:
                    print(f'流水线执行失败: {context.error_str}')
                    return self.round_fail(f'流水线执行失败: {context.error_str}')
                # 获取处理结果
                filtered_contours = context.contours
                if not filtered_contours:
                    print('未检测到驱动盘方格')
                    return self.round_fail('未检测到驱动盘方格')
                print(f'检测到{position}号位的{len(filtered_contours)}个驱动盘方格')
                print('开始绘制网格')
                crop_area=self.ctx.screen_loader.get_area('代理人-驱动盘详细','驱动盘列表')
                crop_rect = crop_area.pc_rect
                all_grids = []
                for contour in filtered_contours:
                   x, y, w, h = cv2.boundingRect(contour)
                   # 转换为绝对坐标
                   absolute_x = x + crop_rect.x1
                   absolute_y = y + crop_rect.y1
                   grid_center = Point(absolute_x + w / 2, absolute_y + h / 2)
                   all_grids.append(grid_center)
                grid_rows = sort_grids(all_grids)
                # 创建包含分区位置和网格信息的字典
                partition_info = {
                    'center': partition_center,  # 分区中心点位置信息
                    'grids': grid_rows     # 分区内各个网格的位置信息
                }
                all_grid_rows.append(partition_info)
        print(f'all_grid_rows={all_grid_rows}')
        return self.round_success('驱动盘方格处理完成',data={'all_grid_rows':all_grid_rows})
    
    @node_from(from_name='驱动盘方格处理')
    @operation_node(name='驱动盘强化')
    def enhance_drive_disk(self):
        #获取all_grid_rows
        prev_node = self.node_status.get('驱动盘方格处理')
        all_grid_rows = prev_node.data.get('all_grid_rows', [])
        #获取驱动盘详细信息区域坐标
        crop_area=self.ctx.screen_loader.get_area('代理人-驱动盘详细','驱动盘详细信息')
        crop_rect=crop_area.pc_rect
        #初始化图片路径
        test_pictures_path=Path(__file__).parent.parent.parent.parent.parent / '.debug' / 'drive_disk_enhance_test_pictures'
        cropped_test_pictures_path=Path(__file__).parent.parent.parent.parent.parent / '.debug' / 'drive_disk_enhance_test_pictures' / 'cropped'
        # 创建目录（如果不存在）
        test_pictures_path.mkdir(parents=True, exist_ok=True)
        cropped_test_pictures_path.mkdir(parents=True, exist_ok=True)
        for partition_info in all_grid_rows:
            #初始化分区中心位置和网格信息
            center = partition_info['center']
            grid_rows = partition_info['grids']
            self.ctx.controller.click(center)
            print(f'驱动盘强化节点点击了{center}')
            time.sleep(1)
            #初始化轮次
            loop_count = 0
            max_loops=50
            while True:
                loop_count += 1
                if loop_count >= max_loops:
                    print(f'超过最大轮次{max_loops}次,自动结束')
                    break

                #清空test_pictures_path
                images = list(test_pictures_path.glob('*.png'))
                for image_path in images:
                    os.remove(image_path)
                images = list(cropped_test_pictures_path.glob('*.png'))
                for image_path in images:
                    os.remove(image_path)
                #截取所有驱动盘图片
                self.ctx.controller.click(self.confirm_rect.center)#初始化令鼠标点击确认按钮
                for row_index,row in enumerate(grid_rows):
                    for col_index,point in enumerate(row):
                        self.ctx.controller.click(point)
                        time.sleep(1)
                        screen = self.ctx.controller.get_screenshot()
                        cv2.imwrite(os.path.join(test_pictures_path, f'grid_{row_index}_{col_index}.png'), screen)
                #读取所有捕获的图片,提交ocr任务
                images = list(test_pictures_path.glob('*.png'))
                for image_path in images:
                    image=cv2.imread(image_path)
                    if image is not None:
                        cropped_image = crop_image_only(image, crop_rect)
                        cv2.imwrite(str(cropped_test_pictures_path / f'cropped_{image_path.stem}.png'), cropped_image)
                        self.ocr_worker.submit('disc',cropped_image,self.parser)
                    else:
                        print(f'无法读取图片 {image_path}')
                #等待ocr完成任务
                self.ocr_worker.wait_complete()
                scanned_discs = self.ocr_worker.scanned_discs
                mapped_discs=DriveDiskMapper.map_discs(scanned_discs)
                #将获取的驱动盘信息写入json文件
                with open(test_pictures_path / 'scanned_discs.json', 'w', encoding='utf-8') as f:
                    f.write(json.dumps(mapped_discs, ensure_ascii=False, indent=2))
                    print("JSON数据已写入文件: scanned_discs.json")
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
                    print(f'驱动盘索引值:{index},潜力值:{potential_score:.2f},潜力评分公式: (副属性权重:{potential_subPropertiesWeight:.2f}+主属性权重:{potential_mainPropertyWeight:.2f})*品质权重:{potential_qualityWeight:.2f}*等级权重:{potential_levelWeight:.2f}*每权重分值:{55/potential_maxWeightSum:.2f}\n有效属性:{potential_validProperties}')
                max_index=potentialScores.index(max(potentialScores))
                row=max_index//4 or 0
                col=max_index%4 or 0
                point=grid_rows[row][col]
                self.ctx.controller.click(point)
                screen = self.ctx.controller.get_screenshot()
                cropped_image = crop_image_only(screen, crop_rect)
                self.ocr_worker.submit('disc',cropped_image,self.parser)
                self.ocr_worker.wait_complete()
                scanned_disc = self.ocr_worker.scanned_discs[0]
                level=scanned_disc['level']
                self.ocr_worker.reset()#重置ocr_worker
                if level>=15:
                    print('当前已取得最优解,结束强化')
                    break
                #print(f'当前最佳驱动盘等级{level}')
                else:
                    self.ctx.controller.click(self.reinforce_rect.center)
                    time.sleep(0.5)
                    self.ctx.controller.click(self.add_stage_rect.center)
                    time.sleep(0.5)
                    self.ctx.controller.click(self.upgrade_rect.center)
                    time.sleep(0.5)
                    self.ctx.controller.click(self.button_close_rect.center)
                    time.sleep(1)
        return self.round_success('驱动盘扫描强化完成')
    #def execute(self):
    #     # 这里可以实现驱动盘强化的具体逻辑
    #     return super().execute()

