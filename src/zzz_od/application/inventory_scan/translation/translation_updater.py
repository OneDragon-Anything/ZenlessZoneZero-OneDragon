import json
import os
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.error import HTTPError, URLError

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log


class TranslationUpdater:
    """翻译字典更新器"""

    API_URLS = {
        'character': 'https://api.hakush.in/zzz/data/character.json',
        'weapon': 'https://api.hakush.in/zzz/data/weapon.json',
        'equipment': 'https://api.hakush.in/zzz/data/equipment.json',
    }

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

            # 更新角色
            log.info("正在下载角色数据...")
            char_data = self._download_json(self.API_URLS['character'])
            if char_data is None:
                log.error("角色数据下载失败，取消更新")
                TranslationUpdater._failed_this_run = True
                return False
            translation_dict['character'] = char_data
            log.info(f"角色数据更新完成，共{len(translation_dict['character'])}个")

            # 更新音擎
            log.info("正在下载音擎数据...")
            weapon_data = self._download_json(self.API_URLS['weapon'])
            if weapon_data is None:
                log.error("音擎数据下载失败，取消更新")
                TranslationUpdater._failed_this_run = True
                return False
            translation_dict['weapon'] = weapon_data
            log.info(f"音擎数据更新完成，共{len(translation_dict['weapon'])}个")

            # 更新驱动盘
            log.info("正在下载驱动盘数据...")
            equipment_data = self._download_json(self.API_URLS['equipment'])
            if equipment_data is None:
                log.error("驱动盘数据下载失败，取消更新")
                TranslationUpdater._failed_this_run = True
                return False
            translation_dict['equipment'] = equipment_data
            log.info(f"驱动盘数据更新完成，共{len(translation_dict['equipment'])}个")

            # 保存字典
            self._save_dict(translation_dict)
            log.info(f"翻译字典已保存到: {self.dict_path}")
            
            # 下载图标（翻译更新完成后自动下载）
            self._download_icons()
            
            return True

        except Exception as e:
            log.error(f"更新翻译字典失败: {e}")
            TranslationUpdater._failed_this_run = True
            return False

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

    def _download_icons(self):
        """下载图标（翻译更新完成后自动下载）"""
        try:
            log.info("开始下载图标...")
            from .icon_downloader import IconDownloader
            downloader = IconDownloader()
            # 强制下载图标（跳过时间检查）
            downloader.download_all()
        except Exception as e:
            log.error(f"下载图标失败: {e}")


def __debug():
    """测试更新"""
    updater = TranslationUpdater()
    updater.update_all()


if __name__ == '__main__':
    __debug()