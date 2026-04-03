import json
import os
import urllib.request
from datetime import datetime
from typing import Dict, Optional
from urllib.error import HTTPError, URLError

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log


class TranslationUpdater:
    """翻译字典更新器"""

    # 类级别标志：同一次运行中如果已经失败过，就不再尝试
    _failed_this_run = False

    def __init__(self):
        # 保存原始JSON到 assets/wiki_data
        self.dict_path = os.path.join(
            os_utils.get_path_under_work_dir('assets', 'wiki_data'),
            'zzz_translation.json'
        )

    def update_if_needed(self) -> bool:
        """如果需要则更新（每天一次）"""
        # 在离线/被403时，优先使用旧字典，不做联网更新
        if os.environ.get('OD_OFFLINE', '').strip() == '1':
            return False
        # 同一次运行中，如果已经失败过，就不要再尝试了（避免重复请求）
        if TranslationUpdater._failed_this_run:
            return False
        if not self._should_update():
            return False
        return self.update_all()

    def _should_update(self) -> bool:
        """检查是否需要更新（每周一次）"""
        if not os.path.exists(self.dict_path):
            log.info(f"翻译字典文件不存在: {self.dict_path}")
            return True

        try:
            # 获取文件修改时间
            mtime = os.path.getmtime(self.dict_path)
            modified_date = datetime.fromtimestamp(mtime)
            
            # 获取当前时间
            now = datetime.now()
            
            # 计算相差天数
            days_diff = (now - modified_date).days
            
            log.info(f"翻译字典最后修改: {modified_date}, 距今 {days_diff} 天")
            
            # 7天内不更新
            return days_diff >= 7
        except Exception as e:
            log.error(f"检查更新时间失败: {e}")
            return True

    def update_all(self) -> bool:
        """更新所有翻译数据"""
        try:
            translation_dict = {
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'character': {},
                'weapon': {},
                'equipment': {}
            }

            # 从本地 agent_state 目录获取角色数据
            log.info("正在从本地 agent_state 目录获取角色数据...")
            char_data = self._get_character_data_from_local()
            if char_data is None:
                log.error("角色数据获取失败，取消更新")
                TranslationUpdater._failed_this_run = True
                return False
            translation_dict['character'] = char_data
            log.info(f"角色数据更新完成，共{len(translation_dict['character'])}个")
            
            # 打印前几个角色数据，确认格式正确
            if char_data:
                first_chars = list(char_data.items())[:3]
                log.info(f"前3个角色数据: {first_chars}")

            # 音擎和驱动盘暂时保持空字典
            log.info("音擎和驱动盘数据保持为空")
            translation_dict['weapon'] = {}
            translation_dict['equipment'] = {}

            # 保存字典
            log.info(f"准备保存字典到: {self.dict_path}")
            self._save_dict(translation_dict)
            log.info(f"翻译字典已保存到: {self.dict_path}")
            
            # 验证文件是否存在
            if os.path.exists(self.dict_path):
                log.info(f"文件已成功创建，大小: {os.path.getsize(self.dict_path)} 字节")
            else:
                log.error(f"文件创建失败，路径: {self.dict_path}")
            
            return True

        except Exception as e:
            log.error(f"更新翻译字典失败: {e}")
            import traceback
            log.error(traceback.format_exc())
            TranslationUpdater._failed_this_run = True
            return False

    def _get_character_data_from_local(self) -> Optional[Dict]:
        """从本地 agent_state 目录获取角色数据"""
        try:
            import yaml
            agent_state_dir = os.path.join(
                os_utils.get_path_under_work_dir('assets', 'template'),
                'agent_state'
            )
            
            if not os.path.exists(agent_state_dir):
                log.error(f"agent_state 目录不存在: {agent_state_dir}")
                return None
            
            character_data = {}
            processed_agents = set()
            
            # 遍历 agent_state 目录下的所有子目录
            for subdir in os.listdir(agent_state_dir):
                subdir_path = os.path.join(agent_state_dir, subdir)
                if not os.path.isdir(subdir_path):
                    continue
                
                # 跳过通用状态目录
                skip_dirs = ['energy', 'guard_break', 'life_deduction', 'ultimate', 'switch_ban', 'special']
                if any(subdir.startswith(skip_dir) for skip_dir in skip_dirs):
                    continue
                
                # 读取 config.yml 文件
                config_path = os.path.join(subdir_path, 'config.yml')
                if not os.path.exists(config_path):
                    log.warning(f"config.yml 文件不存在: {config_path}")
                    continue
                
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                        
                    # 提取 template_id 和 template_name
                    template_id = config.get('template_id', '')
                    template_name = config.get('template_name', '')
                    
                    if not template_id or not template_name:
                        log.warning(f"template_id 或 template_name 不存在: {config_path}")
                        continue
                    
                    # 从 template_id 提取英文名称（如 alice_2_1 -> alice）
                    en_name = template_id.split('_')[0]
                    
                    # 跳过通用状态
                    skip_names = ['energy', 'guard_break', 'life_deduction', 'ultimate', 'switch_ban', 'special', 'life']
                    if en_name in skip_names:
                        continue
                    
                    # 从 template_name 提取中文名称（如 角色状态-爱丽丝-21 -> 爱丽丝）
                    chs_name = template_name.split('-')[1] if len(template_name.split('-')) > 1 else ''
                    
                    if not en_name or not chs_name:
                        log.warning(f"无法提取角色名称: {config_path}")
                        continue
                    
                    # 避免重复处理同一个角色
                    if en_name not in processed_agents:
                        processed_agents.add(en_name)
                        # 构建角色数据
                        character_data[en_name] = {
                            'CHS': chs_name,
                            'EN': en_name,
                            'code': en_name
                        }
                        log.debug(f"添加角色: {en_name} -> {chs_name}")
                        
                except Exception as e:
                    log.error(f"读取 {config_path} 失败: {e}")
                    continue
            
            if not character_data:
                log.warning("未找到角色数据")
                return None
            
            return character_data
            
        except Exception as e:
            log.error(f"从本地获取角色数据失败: {e}")
            return None

    def _download_json(self, url: str) -> Optional[Dict]:
        """下载JSON数据"""
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
                # 验证JSON有效性
                try:
                    json_content = json.loads(data)
                    return json_content
                except json.JSONDecodeError:
                    log.error(f"下载的JSON格式无效: {url}")
                    return None
        except HTTPError as e:
            log.error(f"下载失败 (HTTP {e.code}): {url}")
        except URLError as e:
            log.error(f"下载失败 (URL Error): {url} {e.reason}")
        except Exception as e:
            log.error(f"下载失败: {url} {str(e)}")
        return None

    def _save_dict(self, translation_dict: Dict):
        """保存翻译字典"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.dict_path), exist_ok=True)
        # 保存完整JSON数据
        with open(self.dict_path, 'w', encoding='utf-8') as f:
            json.dump(translation_dict, f, ensure_ascii=False, indent=2)

def __debug():
    """测试更新"""
    print("开始测试更新...")
    updater = TranslationUpdater()
    print(f"字典保存路径: {updater.dict_path}")
    print("执行更新...")
    result = updater.update_all()
    print(f"更新结果: {result}")


if __name__ == '__main__':
    __debug()
