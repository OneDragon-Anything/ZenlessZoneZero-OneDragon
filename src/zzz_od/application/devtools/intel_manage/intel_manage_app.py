from pathlib import Path
from typing import Dict

import yaml
from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.utils.log_utils import log
from one_dragon.utils.os_utils import get_resource_path
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.application.devtools.intel_manage import intel_manage_const
from zzz_od.game_data.agent import AgentTypeEnum, DmgTypeEnum


class IntelManageApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=intel_manage_const.APP_ID,
            op_name=intel_manage_const.APP_NAME,
            node_max_retry_times=1,
            timeout_seconds=-1,
            op_callback=None,
            need_check_game_win=False,
        )
        self.agent_data: Dict[str, dict] = {}

    def _execute(self) -> None:
        log.info('信息管理应用执行')

    def load_agent_data(self) -> Dict[str, dict]:
        """加载所有代理人数据（业务逻辑）"""
        self.agent_data = {}
        agent_dir = Path(get_resource_path('assets', 'game_data', 'agent'))

        if not agent_dir.exists():
            log.warning(f"Agent directory not found: {agent_dir}")
            return self.agent_data

        agent_type_mapping = self._get_enum_mapping(AgentTypeEnum)
        dmg_type_mapping = self._get_enum_mapping(DmgTypeEnum)

        # 使用 Enum 获取类型映射（复用公共方法）

        for yml_file in agent_dir.glob('*.yml'):
            if yml_file.name.startswith('_'):
                continue
            
            if '..' in yml_file.name or '/' in yml_file.name or '\\' in yml_file.name:
                log.warning(f'跳过包含非法字符的文件: {yml_file.name}')
                continue

            try:
                with open(yml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
            except (IOError, yaml.YAMLError) as e:
                log.error(f'文件读取或解析错误 {yml_file}: {e}')
                continue
            except Exception as e:
                log.error(f'未知错误 {yml_file}: {e}')
                continue

            if data and 'agent_name' in data:
                # 转换类型为中文
                if 'agent_type' in data and data['agent_type'] in agent_type_mapping:
                    data['agent_type_cn'] = agent_type_mapping[data['agent_type']]
                else:
                    data['agent_type_cn'] = data.get('agent_type', '')

                if 'dmg_type' in data and data['dmg_type'] in dmg_type_mapping:
                    data['dmg_type_cn'] = dmg_type_mapping[data['dmg_type']]
                else:
                    data['dmg_type_cn'] = data.get('dmg_type', '')

                self.agent_data[data['agent_name']] = data

        log.info(f"Loaded {len(self.agent_data)} agents")
        return self.agent_data

    def _get_safe_filename(self, agent_name: str, agent_data: dict) -> str | None:
        """生成安全的文件名（防止路径遍历攻击）"""
        code = agent_data.get('code', '')
        
        safe_name = Path(code).name if code else Path(agent_name.lower().replace(' ', '_')).name
        file_name = safe_name + '.yml'
        
        if '..' in file_name or '/' in file_name or '\\' in file_name:
            log.error(f'文件名包含非法字符: {file_name}')
            return None
        
        return file_name

    def save_agent_data(self, agent_name: str, agent_data: dict) -> bool:
        """保存代理人数据（业务逻辑）"""
        try:
            agent_dir = Path(get_resource_path('assets', 'game_data', 'agent'))
            agent_dir.mkdir(parents=True, exist_ok=True)

            # 生成安全的文件名
            file_name = self._get_safe_filename(agent_name, agent_data)
            if not file_name:
                return False
            
            file_path = agent_dir / file_name

            # 使用 YamlOperator 保存
            yaml_op = YamlOperator(str(file_path))
            yaml_op.data = agent_data
            yaml_op.save()

            log.info(f"Saved agent data to: {file_path}")
            return True
        except Exception as e:
            log.error(f'Failed to save agent data: {e}')
            return False

    def _get_enum_mapping(self, enum_class) -> Dict[str, str]:
        """获取枚举类型映射（英文名称到中文值），排除UNKNOWN"""
        return {e.name: e.value for e in enum_class if e.name != 'UNKNOWN'}

    def get_agent_type_mapping(self) -> Dict[str, str]:
        """获取角色类型映射（英文到中文）"""
        return self._get_enum_mapping(AgentTypeEnum)

    def get_dmg_type_mapping(self) -> Dict[str, str]:
        """获取属性类型映射（英文到中文）"""
        return self._get_enum_mapping(DmgTypeEnum)
