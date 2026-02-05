import os
import json
import urllib.request
import time
from urllib.error import HTTPError, URLError

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log


class IconDownloader:
    """游戏图标下载器"""

    BASE_URL = "https://api.hakush.in/zzz/UI/"
    
    # 静态图标列表
    STATIC_ICONS = [
        # 技能图标
        "Icon_Normal.webp",
        "Icon_Evade.webp",
        "Icon_SpecialReady.webp",
        "Icon_UltimateReady.webp",
        "Icon_Switch.webp",
        "Icon_CoreSkill.webp",
        # 属性图标
        "IconPhysical.webp",
        "IconFire.webp",
        "IconIce.webp",
        "IconElectric.webp",
        "IconEther.webp",
        # 武器类型图标
        "IconAttackType.webp",
        "IconStun.webp",
        "IconAnomaly.webp",
        "IconDefense.webp",
        "IconRupture.webp",
        "IconSupport.webp",
    ]

    # 类级别标志：同一次运行中如果已经失败过，就不再尝试
    _failed_this_run = False

    def __init__(self):
        # 图标保存路径：assets/wiki_data/icons/
        self.icons_dir = os.path.join(
            os_utils.get_path_under_work_dir('assets', 'wiki_data'),
            'icons'
        )
        # 翻译数据路径
        self.translation_path = os.path.join(
            os_utils.get_path_under_work_dir('assets', 'wiki_data'),
            'zzz_translation.json'
        )

    def download_if_needed(self) -> bool:
        """检测并下载图标（每次都检测缺失的图标）"""
        log.info(f"检查是否需要下载图标...")
        
        # 离线模式
        if os.environ.get('OD_OFFLINE', '').strip() == '1':
            log.info("离线模式，跳过图标下载")
            return False
        # 同一次运行中如果已经失败过，就不再尝试
        if IconDownloader._failed_this_run:
            log.info("本次运行已失败过，跳过图标下载")
            return False
        
        # 直接下载，_download_file 会跳过已存在的文件
        return self.download_all()

    def _should_update(self) -> bool:
        """检查是否需要更新（每周一次）"""
        if not os.path.exists(self.icons_dir):
            return True
        
        # 检查目录下是否有任何图标文件
        try:
            files = os.listdir(self.icons_dir)
            if not files:
                return True
            
            # 检查最近修改的文件
            latest_mtime = 0
            for f in files:
                filepath = os.path.join(self.icons_dir, f)
                if os.path.isfile(filepath):
                    mtime = os.path.getmtime(filepath)
                    if mtime > latest_mtime:
                        latest_mtime = mtime
            
            # 计算相差天数
            now = time.time()
            days_diff = (now - latest_mtime) / (24 * 3600)
            
            # 7天内不更新
            return days_diff >= 7
        except Exception:
            return True

    def download_all(self) -> bool:
        """下载所有图标"""
        try:
            # 确保目录存在
            os.makedirs(self.icons_dir, exist_ok=True)
            
            # 1. 下载静态图标
            log.info("开始下载静态图标...")
            static_count = self._download_static_icons()
            log.info(f"静态图标下载完成，共 {static_count} 个")
            
            # 2. 下载角色图标
            log.info("开始下载角色图标...")
            char_count = self._download_character_icons()
            log.info(f"角色图标下载完成，共 {char_count} 个")
            
            log.info(f"图标下载完成，保存到: {self.icons_dir}")
            return True
            
        except Exception as e:
            log.error(f"图标下载失败: {e}")
            IconDownloader._failed_this_run = True
            return False

    def _download_static_icons(self) -> int:
        """下载静态图标"""
        count = 0
        for filename in self.STATIC_ICONS:
            url = f"{self.BASE_URL}{filename}"
            filepath = os.path.join(self.icons_dir, filename)
            if self._download_file(url, filepath):
                count += 1
        return count

    def _download_character_icons(self) -> int:
        """下载角色图标（只下载圆头和半身）"""
        count = 0
        
        # 读取翻译数据
        if not os.path.exists(self.translation_path):
            log.warning(f"翻译数据文件不存在: {self.translation_path}")
            return 0
        
        try:
            with open(self.translation_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            character_data = data.get('character', {})
            
            for char_id, char_info in character_data.items():
                icon_code = char_info.get("icon")
                if icon_code:
                    # 圆头 (IconRolexx -> IconRoleCirclexx)
                    if "IconRole" in icon_code:
                        circle_code = icon_code.replace("IconRole", "IconRoleCircle")
                        circle_filename = f"{circle_code}.webp"
                        circle_url = f"{self.BASE_URL}{circle_filename}"
                        circle_filepath = os.path.join(self.icons_dir, circle_filename)
                        if self._download_file(circle_url, circle_filepath):
                            count += 1
                    
                    # 半身 (IconRolexx -> IconRoleCropxx)
                    if "IconRole" in icon_code:
                        crop_code = icon_code.replace("IconRole", "IconRoleCrop")
                        crop_filename = f"{crop_code}.webp"
                        crop_url = f"{self.BASE_URL}{crop_filename}"
                        crop_filepath = os.path.join(self.icons_dir, crop_filename)
                        if self._download_file(crop_url, crop_filepath):
                            count += 1
            
        except Exception as e:
            log.error(f"处理角色图标失败: {e}")
        
        return count

    def _download_file(self, url: str, filepath: str) -> bool:
        """下载单个文件（带重试机制）"""
        # 文件已存在则跳过
        if os.path.exists(filepath):
            return True
        
        # 最多重试 3 次
        max_retries = 3
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=60) as response:
                    with open(filepath, 'wb') as out_file:
                        out_file.write(response.read())
                return True
            except HTTPError as e:
                log.error(f"下载失败 (HTTP {e.code}): {url}")
                break  # HTTP 错误不重试
            except URLError as e:
                if attempt < max_retries - 1:
                    log.warning(f"下载失败，重试 {attempt + 1}/{max_retries}: {url} {e.reason}")
                    time.sleep(1)  # 等待 1 秒后重试
                else:
                    log.error(f"下载失败 (URL Error): {url} {e.reason}")
            except Exception as e:
                if attempt < max_retries - 1:
                    log.warning(f"下载失败，重试 {attempt + 1}/{max_retries}: {url} {str(e)}")
                    time.sleep(1)
                else:
                    log.error(f"下载失败: {url} {str(e)}")
        return False


def __debug():
    """测试下载"""
    downloader = IconDownloader()
    downloader.download_all()


if __name__ == '__main__':
    __debug()