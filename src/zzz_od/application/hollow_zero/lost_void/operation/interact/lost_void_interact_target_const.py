from enum import Enum
from typing import Optional, Union

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import LostVoidRegionType
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum, Agent


class LostVoidInteractNPC(Enum):

    """
    可交互的NPC名称
    """
    MA_LIN = '玛琳'  # 挚交会谈 左边重置路线的
    AO_FEI_LI_YA = '奥菲莉亚'  # 代理人武备
    LEI = '蕾'  # 通用武备
    SCGMDYJY = '神出鬼没的研究员'  # 2.0版本 特遣调查 入口
    A_YUAN = '阿援'  # 挚交会谈 商店
    GUAI_ZAI = '乖仔'  # 抽奖机


class LostVoidBoss(Enum):

    """
    最终入口交互的BOSS名称
    """
    SHENG_GUI = '终结之役·牲鬼'
    JIE_PEI_TUO = '终结之役·杰佩托'


class LostVoidInteractTarget:

    def __init__(self, name: str, icon: str,
                 is_agent: bool = False,
                 is_npc: bool = False,
                 is_entry: bool = False,
                 is_exclamation: bool = False,
                 is_distance: bool = False,
                 after_battle: bool = False):
        self.name: str = name  # 交互显示的文本
        self.icon: str = icon  # 交互显示的图标
        self.is_agent: bool = is_agent  # 是否和代理人交互
        self.is_npc: bool = is_npc  # 是否和NPC交互
        self.is_entry: bool = is_entry  # 是否和下层入口交互
        self.is_exclamation: bool = is_exclamation  # 是否和感叹号交互 没有识别文本时就是这个
        self.is_distance: bool = is_distance  # 是否白点距离
        self.after_battle: bool = after_battle  # 是否战斗后的交互




def match_interact_target(ctx: ZContext, ocr_result: str,) -> Optional[LostVoidInteractTarget]:
    """
    匹配具体的交互目标
    @param ctx: 上下文
    @param ocr_result: 识别的交互文本
    @return: 交互目标
    """
    # 删除一些交互时候可能识别到的特殊字符
    ocr_result = ocr_result.replace('<', '')
    ocr_result = ocr_result.replace('>', '')
    if len(ocr_result) == 0:
        return None

    target_list: list[Union[str, Agent]] = (
            [i.value.value for i in LostVoidRegionType]  # 入口
            + [i.value for i in LostVoidInteractNPC]  # NPC
            + [i.value for i in AgentEnum]  # 代理人
            + [i.value for i in LostVoidBoss]  # BOSS
    )
    target_word_list: list[str] = (
        [gt(i.value.value, 'game') for i in LostVoidRegionType]  # 入口
        + [gt(i.value, 'game') for i in LostVoidInteractNPC]  # NPC
        + [gt(i.value.agent_name, 'game') for i in AgentEnum]  # 代理人
        + [gt(i.value, 'game') for i in LostVoidBoss]  # BOSS
    )

    idx = str_utils.find_best_match_by_difflib(ocr_result, target_word_list, cutoff=0.6)
    if idx is None:
        return None

    start_idx: int = 0
    end_idx: int = start_idx + len(LostVoidRegionType)

    if start_idx <= idx < end_idx:
        return LostVoidInteractTarget(name=target_list[idx], icon=target_list[idx], is_entry=True)

    start_idx = end_idx
    end_idx = start_idx + len(LostVoidInteractNPC)
    if start_idx <= idx < end_idx:
        return LostVoidInteractTarget(name=target_list[idx], icon='感叹号', is_npc=True)

    start_idx = end_idx
    end_idx = start_idx + len(AgentEnum)
    if start_idx <= idx < end_idx:
        return LostVoidInteractTarget(name=target_list[idx].agent_name, icon='感叹号', is_agent=True)

    start_idx = end_idx
    end_idx = start_idx + len(LostVoidBoss)
    if start_idx <= idx < end_idx:
        return LostVoidInteractTarget(name=target_list[idx], icon=LostVoidRegionType.BOSS.value.value, is_entry=True)