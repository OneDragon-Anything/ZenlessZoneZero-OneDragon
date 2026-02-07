import csv
import json
from datetime import datetime
from pathlib import Path

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.driver_disc_read import driver_disc_read_const
from zzz_od.application.driver_disc_read.drive_disk_exporter import DriveDiskExporter
from zzz_od.application.driver_disc_read.driver_disc_parser import DriverDiscParser
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class DriverDiscExportApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=driver_disc_read_const.EXPORT_APP_ID,
            op_name=gt(driver_disc_read_const.EXPORT_APP_NAME),
        )
        self.parser = DriverDiscParser()
        self.exporter = DriveDiskExporter()

    @operation_node(name='导入CSV', is_start_node=True)
    def import_csv(self):
        """
        从 import 目录导入 CSV 文件到缓存
        """
        import_dir = Path(os_utils.get_path_under_work_dir('import'))
        import_file = import_dir / 'driver_disc.csv'

        if not import_file.exists():
            return self.round_fail(f'未找到导入文件: {import_file.name}，请将文件放入 import 目录')

        try:
            data_list = []
            with open(import_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data_list.append(dict(row))
            
            if not data_list:
                return self.round_fail('CSV文件为空')

            # 保存到缓存
            cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / 'cache.json'
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data_list, f, ensure_ascii=False, indent=4)
            
            return self.round_success(f'已导入 {len(data_list)} 条数据，即将开始清洗')
        except Exception as e:
            return self.round_fail(f'导入失败: {e}')

    @node_from(from_name='导入CSV')
    @operation_node(name='数据清洗', is_start_node=True)
    def clean_data(self):
        """
        读取缓存数据，进行清洗和校验
        """
        cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
        cache_file = cache_dir / 'cache.json'

        if not cache_file.exists():
            return self.round_fail('未找到缓存文件，请先运行识别')

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                raw_data_list = json.load(f)
        except Exception as e:
            return self.round_fail(f'读取缓存失败: {e}')

        cleaned_data = []
        anomalies = []

        for idx, raw_item in enumerate(raw_data_list):
            parsed = self.parser.parse(raw_item)
            
            # 校验逻辑
            is_valid = True
            reasons = []

            if not parsed['name']:
                is_valid = False
                reasons.append('名称为空')
            if not parsed['slot']:
                is_valid = False
                reasons.append('位置未知')
            if not parsed['main_stat']:
                is_valid = False
                reasons.append('主属性为空')
            
            if parsed['level'] >= 3 and not parsed['substats']:
                is_valid = False
                reasons.append('有等级但无副属性')

            if is_valid:
                cleaned_data.append(parsed)
            else:
                anomalies.append({
                    'index': idx,
                    'reasons': reasons,
                    'parsed': parsed,
                    'raw': raw_item
                })

        # 保存清洗后的数据
        cleaned_file = cache_dir / 'driver_disc_cleaned.json'
        with open(cleaned_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=4)

        # 保存异常数据
        anomalies_file = cache_dir / 'driver_disc_anomalies.json'
        with open(anomalies_file, 'w', encoding='utf-8') as f:
            json.dump(anomalies, f, ensure_ascii=False, indent=4)

        msg = f'清洗完成。有效: {len(cleaned_data)}, 异常: {len(anomalies)}。'
        if anomalies:
            msg += f'请查看 {anomalies_file.name} 确认异常数据。'
        
        log.info(msg)
        return self.round_success(msg)

    @node_from(from_name='数据清洗')
    @operation_node(name='导出CSV')
    def export_csv(self):
        """
        导出原始缓存数据为 CSV 格式
        """
        cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
        cache_file = cache_dir / 'cache.json'

        if not cache_file.exists():
            return self.round_fail('未找到缓存文件')

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data_list = json.load(f)
            
            if not data_list:
                return self.round_fail('缓存数据为空')

            export_dir = Path(os_utils.get_path_under_work_dir('export'))
            export_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_file = export_dir / f'driver_disc_{timestamp}.csv'

            # 获取所有可能的字段名作为表头
            fieldnames = set()
            for item in data_list:
                fieldnames.update(item.keys())
            
            # 排序字段：name, slot, level, rating, main_stat...
            sorted_fields = ['name', 'slot', 'level', 'rating', 'main_stat', 'main_stat_value']
            other_fields = sorted(list(fieldnames - set(sorted_fields)))
            fieldnames = sorted_fields + other_fields

            with open(export_file, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data_list)

            return self.round_success(f'CSV已导出至: {export_file.name}')
        except Exception as e:
            return self.round_fail(f'导出CSV失败: {e}')

    @node_from(from_name='导出CSV')
    @operation_node(name='导出原始数据')
    def export_raw_data(self):
        """
        导出原始缓存数据到 export 目录
        """
        cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
        cache_file = cache_dir / 'cache.json'

        if not cache_file.exists():
            return self.round_fail('未找到缓存文件')

        export_dir = Path(os_utils.get_path_under_work_dir('export'))
        export_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_file = export_dir / f'driver_disc_raw_{timestamp}.json'

        try:
            import shutil
            shutil.copy2(cache_file, export_file)
            return self.round_success(f'原始数据已导出至: {export_file.name}')
        except Exception as e:
            return self.round_fail(f'导出失败: {e}')

    @node_from(from_name='导出原始数据')
    @operation_node(name='导出ZOD格式')
    def export_zod_data(self):
        """
        将清洗后的数据导出为 ZOD 格式
        """
        cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
        cleaned_file = cache_dir / 'driver_disc_cleaned.json'

        if not cleaned_file.exists():
            return self.round_fail('未找到清洗后的数据，请先运行数据清洗')

        try:
            with open(cleaned_file, 'r', encoding='utf-8') as f:
                cleaned_data = json.load(f)
            
            zod_data = self.exporter.convert_to_zod_json(cleaned_data)
            
            export_dir = Path(os_utils.get_path_under_work_dir('export'))
            export_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_file = export_dir / f'driver_disc_zod_{timestamp}.json'
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(zod_data, f, ensure_ascii=False, indent=4)
                
            return self.round_success(f'ZOD格式数据已导出至: {export_file.name}')
        except Exception as e:
            return self.round_fail(f'导出失败: {e}')


def __debug():
    ctx = ZContext()
    ctx.init()
    app = DriverDiscExportApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
