from cv2.typing import MatLike
from enum import Enum
from typing import Optional, List, Union, Tuple

from one_dragon.utils.i18_utils import gt


class AgentTypeEnum(Enum):

    ATTACK = '强攻'
    STUN = '击破'
    SUPPORT = '支援'
    DEFENSE = '防护'
    ANOMALY = '异常'
    RUPTURE = '命破'
    UNKNOWN = '未知'

    @classmethod
    def from_name(cls, name):
        if name in AgentTypeEnum.__members__:
            return cls[name]
        else:
            return cls.UNKNOWN


class DmgTypeEnum(Enum):

    ELECTRIC = '电属性'
    ETHER = '以太属性'
    PHYSICAL = '物理属性'
    FIRE = '火属性'
    ICE = '冰属性'
    UNKNOWN = '未知'

    @classmethod
    def from_name(cls, name):
        if name in DmgTypeEnum.__members__:
            return cls[name]
        else:
            return cls.UNKNOWN

    @classmethod
    def from_value(cls, value: str):
        for name in DmgTypeEnum.__members__:
            enum = cls[name]
            if enum.value == value:
                return enum

        return cls.UNKNOWN


class RareTypeEnum(Enum):

    S = 'S'
    A = 'A'
    UNKNOWN = '未知'

    @classmethod
    def from_name(cls, name):
        if name in RareTypeEnum.__members__:
            return cls[name]
        else:
            return cls.UNKNOWN


class AgentStateCheckWay(Enum):

    COLOR_RANGE_CONNECT: int = 1  # 根据颜色 在特定范围里匹配找连通块的数量
    BACKGROUND_GRAY_RANGE_LENGTH: int = 2  # 根据背景的灰度颜色 在特定范围里反推横条的长度
    COLOR_RANGE_EXIST: int = 3  # 根据颜色 在特定范围里匹配是否出现
    FOREGROUND_COLOR_RANGE_LENGTH: int = 4  # 根据前景颜色 在特定范围里计算横条的长度
    FOREGROUND_GRAY_RANGE_LENGTH: int = 5  # 根据前景的灰度颜色 在特定范围里计算横条的长度
    TEMPLATE_FOUND: int = 6  # 根据模板识别是否存在
    TEMPLATE_NOT_FOUND: int = 7  # 根据模板识别不存在
    COLOR_CHANNEL_MAX_RANGE_EXIST: int = 8  # 根据颜色通道的最大值 在特定范围里匹配是否出现
    COLOR_CHANNEL_EQUAL_RANGE_CONNECT: int = 9  # 在特定范围里匹配找三色相等的像素点数量


class AgentStateDef:

    def __init__(self, state_name: str,
                 check_way: AgentStateCheckWay,
                 template_id: str,
                 lower_color: Union[MatLike, Tuple, int] = None,
                 upper_color: Union[MatLike, Tuple, int] = None,
                 hsv_color: Union[MatLike, Tuple, int] = None,
                 hsv_color_diff: Union[MatLike, Tuple, int] = None,
                 connect_cnt: Optional[int] = None,
                 split_color_range: Optional[List[Union[MatLike, int]]] = None,
                 max_length: int = 100,
                 min_value_trigger_state: Optional[int] = None,
                 template_threshold: Optional[float] = None,
                 ):
        self.state_name: str = state_name
        self.template_id: str = template_id
        self.check_way: AgentStateCheckWay = check_way
        self.should_check_in_battle: bool = True  # 是否需要在战斗中检测 自动战斗开始前进行初始化

        # 需要匹配的颜色范围RGB
        self.lower_color: Union[MatLike, int] = lower_color
        self.upper_color: Union[MatLike, int] = upper_color

        # 需要匹配的颜色范围HVS
        self.hsv_color: Union[MatLike, int] = hsv_color
        self.hsv_color_diff: Union[MatLike, int] = hsv_color_diff

        # 匹配用于分割的颜色范围 类似能量条的中间有空白时使用
        self.split_color_range: Optional[List[Union[MatLike, int]]] = split_color_range

        # 判断连通块时 所需的最小像素点数量
        self.connect_cnt: Optional[int] = connect_cnt

        # 判断长度时 用于调整最大长度 例如能量最大值是120
        self.max_length: int = max_length

        # 触发这个状态的最小状态值
        self.min_value_trigger_state: int = 0  # 默认为0 即有识别就触发
        if min_value_trigger_state is not None:
            self.min_value_trigger_state = min_value_trigger_state
        elif self.check_way == AgentStateCheckWay.COLOR_RANGE_EXIST:
            # 判断存在与否的话 默认为1 即只有存在的时候才触发记录
            self.min_value_trigger_state = 1

        # 模板匹配
        self.template_threshold: float = template_threshold


class CommonAgentStateEnum(Enum):

    ENERGY_31 = AgentStateDef('前台-能量', AgentStateCheckWay.FOREGROUND_GRAY_RANGE_LENGTH,
                              lower_color=90, upper_color=255, template_id='energy_3_1',
                              split_color_range=[0, 30], max_length=120)
    ENERGY_32 = AgentStateDef('后台-1-能量', AgentStateCheckWay.FOREGROUND_GRAY_RANGE_LENGTH,
                              lower_color=90, upper_color=255, template_id='energy_3_2',
                              split_color_range=[0, 30], max_length=120)
    ENERGY_33 = AgentStateDef('后台-2-能量', AgentStateCheckWay.FOREGROUND_GRAY_RANGE_LENGTH,
                              lower_color=90, upper_color=255, template_id='energy_3_3',
                              split_color_range=[0, 30], max_length=120)
    ENERGY_21 = AgentStateDef('前台-能量', AgentStateCheckWay.FOREGROUND_GRAY_RANGE_LENGTH,
                              lower_color=90, upper_color=255, template_id='energy_2_1',
                              split_color_range=[0, 30], max_length=120)
    ENERGY_22 = AgentStateDef('后台-1-能量', AgentStateCheckWay.FOREGROUND_GRAY_RANGE_LENGTH,
                              lower_color=90, upper_color=255, template_id='energy_2_2',
                              split_color_range=[0, 30], max_length=120)

    SPECIAL_31 = AgentStateDef('前台-特殊技可用', AgentStateCheckWay.COLOR_RANGE_CONNECT,
                               template_id='special_3_1', hsv_color=(0, 0, 255), hsv_color_diff=(90, 255, 50),
                                     connect_cnt=200)
    SPECIAL_32 = AgentStateDef('后台-1-特殊技可用', AgentStateCheckWay.COLOR_CHANNEL_MAX_RANGE_EXIST,
                               template_id='energy_3_2', min_value_trigger_state=0,  # 不存在的时候 也需要触发一个清除
                               lower_color=150, upper_color=255, connect_cnt=10)
    SPECIAL_33 = AgentStateDef('后台-2-特殊技可用', AgentStateCheckWay.COLOR_CHANNEL_MAX_RANGE_EXIST,
                               template_id = 'energy_3_3', min_value_trigger_state=0,  # 不存在的时候 也需要触发一个清除
                               lower_color=150, upper_color=255, connect_cnt=10)
    SPECIAL_21 = AgentStateDef('前台-特殊技可用', AgentStateCheckWay.COLOR_RANGE_CONNECT,
                               template_id='special_3_1', hsv_color=(0, 0, 255), hsv_color_diff=(90, 255, 50),
                                     connect_cnt=200)
    SPECIAL_22 = AgentStateDef('后台-1-特殊技可用', AgentStateCheckWay.COLOR_CHANNEL_MAX_RANGE_EXIST,
                               template_id='energy_2_2', min_value_trigger_state=0,  # 不存在的时候 也需要触发一个清除
                               lower_color=150, upper_color=255, connect_cnt=10)

    ULTIMATE_31 = AgentStateDef('前台-终结技可用', AgentStateCheckWay.COLOR_RANGE_CONNECT,
                                template_id='ultimate_3_1', hsv_color=(0, 0, 255), hsv_color_diff=(90, 255, 50),
                                     connect_cnt=1000)
    ULTIMATE_32 = AgentStateDef('后台-1-终结技可用', AgentStateCheckWay.COLOR_RANGE_EXIST,
                                template_id='ultimate_3_2', min_value_trigger_state=0,  # 不存在的时候 也需要触发一个清除
                                lower_color=(250, 150, 20), upper_color=(255, 255, 70), connect_cnt=5)
    ULTIMATE_33 = AgentStateDef('后台-2-终结技可用', AgentStateCheckWay.COLOR_RANGE_EXIST,
                                template_id='ultimate_3_3', min_value_trigger_state=0,  # 不存在的时候 也需要触发一个清除
                                lower_color=(250, 150, 20), upper_color=(255, 255, 70), connect_cnt=5)
    ULTIMATE_21 = AgentStateDef('前台-终结技可用', AgentStateCheckWay.COLOR_RANGE_CONNECT,
                                template_id='ultimate_3_1', hsv_color=(0, 0, 255), hsv_color_diff=(90, 255, 50),
                                     connect_cnt=1000)
    ULTIMATE_22 = AgentStateDef('后台-1-终结技可用', AgentStateCheckWay.COLOR_RANGE_EXIST,
                                template_id='ultimate_2_2', min_value_trigger_state=0,  # 不存在的时候 也需要触发一个清除
                                lower_color=(250, 150, 20), upper_color=(255, 255, 70), connect_cnt=5)

    LIFE_DEDUCTION_31 = AgentStateDef('前台-血量扣减', AgentStateCheckWay.FOREGROUND_COLOR_RANGE_LENGTH,
                                   lower_color=(140, 30, 30), upper_color=(160, 50, 50), template_id='life_deduction_3_1',
                                   min_value_trigger_state=1)
    LIFE_DEDUCTION_21 = AgentStateDef('前台-血量扣减', AgentStateCheckWay.FOREGROUND_COLOR_RANGE_LENGTH,
                                   lower_color=(140, 30, 30), upper_color=(160, 50, 50), template_id='life_deduction_2_1',
                                   min_value_trigger_state=1)

    GUARD_BREAK = AgentStateDef('格挡破碎', AgentStateCheckWay.COLOR_CHANNEL_EQUAL_RANGE_CONNECT,
                              template_id='guard_break', min_value_trigger_state=1,  # 只在检测到时触发
                              lower_color=0, upper_color=255, connect_cnt=10000)  # 需要足够多的面积保证不会误判



class Agent:

    def __init__(self, agent_id: str, agent_name: str,
                 rare_type: RareTypeEnum,
                 agent_type: AgentTypeEnum,
                 dmg_type: DmgTypeEnum,
                 template_id_list: list[str],
                 state_list: Optional[List[AgentStateDef]] = None,
                 ):
        """
        代理人
        """
        self.agent_id: str = agent_id  # 代理人的英文名称
        # 代理人头像的模板ID 不同皮肤的头像会不一样 在启动时由context根据配置写入正确的皮肤
        # 这里没有简单地用template_id_list去遍历可能的头像，主要是效率癖 + 对python运行效率的担忧
        self.template_id: str = agent_id
        self.agent_name: str = agent_name  # 代理人的中文名称
        self.rare_type: RareTypeEnum = rare_type  # 稀有等级

        self.agent_type: AgentTypeEnum = agent_type  # 角色类型
        self.dmg_type: DmgTypeEnum = dmg_type  # 伤害类型

        self.template_id_list: list[str] = template_id_list  # 代理人的头像模板ID列表
        self.state_list: List[AgentStateDef] = state_list  # 可能有的状态

    @property
    def agent_type_str(self) -> str:
        return gt(self.agent_type.value)


class AgentEnum(Enum):

    ANBY = Agent('anby', '安比', RareTypeEnum.A, AgentTypeEnum.STUN, DmgTypeEnum.ELECTRIC, ['anby'])
    ANTON = Agent('anton', '安东', RareTypeEnum.A, AgentTypeEnum.ATTACK, DmgTypeEnum.ELECTRIC, ['anton'])
    BEN = Agent('ben', '本', RareTypeEnum.A, AgentTypeEnum.DEFENSE, DmgTypeEnum.FIRE, ['ben'])
    BILLY = Agent('billy', '比利', RareTypeEnum.A, AgentTypeEnum.ATTACK, DmgTypeEnum.ELECTRIC, ['billy'])
    CORIN = Agent('corin', '可琳', RareTypeEnum.A, AgentTypeEnum.ATTACK, DmgTypeEnum.PHYSICAL, ['corin'])
    ELLEN = Agent('ellen', '艾莲', RareTypeEnum.S, AgentTypeEnum.ATTACK, DmgTypeEnum.ICE, ['ellen', 'ellen_on_campus'],
                  state_list=[AgentStateDef('艾莲-急冻充能', AgentStateCheckWay.COLOR_RANGE_CONNECT,
                                            template_id='ellen', lower_color=(200, 245, 250), upper_color=(255, 255, 255), connect_cnt=2)])
    GRACE = Agent('grace', '格莉丝', RareTypeEnum.S, AgentTypeEnum.ANOMALY, DmgTypeEnum.ELECTRIC, ['grace'])
    KOLEDA = Agent('koleda', '珂蕾妲', RareTypeEnum.S, AgentTypeEnum.STUN, DmgTypeEnum.FIRE, ['koleda'])
    LUCY = Agent('lucy', '露西', RareTypeEnum.A, AgentTypeEnum.SUPPORT, DmgTypeEnum.FIRE, ['lucy'])
    LYCAON = Agent('lycaon', '莱卡恩', RareTypeEnum.S, AgentTypeEnum.STUN, DmgTypeEnum.ICE, ['lycaon'])
    NEKOMATA = Agent('nekomata', '猫又', RareTypeEnum.S, AgentTypeEnum.ATTACK, DmgTypeEnum.PHYSICAL, ['nekomata'])
    NICOLE = Agent('nicole', '妮可', RareTypeEnum.A, AgentTypeEnum.SUPPORT, DmgTypeEnum.ETHER, ['nicole', 'nicole_cunning_cutie'],)
    PIPER = Agent('piper', '派派', RareTypeEnum.A, AgentTypeEnum.ANOMALY, DmgTypeEnum.PHYSICAL, ['piper'])
    RINA = Agent('rina', '丽娜', RareTypeEnum.S, AgentTypeEnum.SUPPORT, DmgTypeEnum.ELECTRIC, ['rina'])
    SOLDIER_11 = Agent('soldier_11', '11号', RareTypeEnum.S, AgentTypeEnum.ATTACK, DmgTypeEnum.FIRE, ['soldier_11'])
    SOUKAKU = Agent('soukaku', '苍角', RareTypeEnum.A, AgentTypeEnum.SUPPORT, DmgTypeEnum.ICE, ['soukaku'],
                  state_list=[AgentStateDef('苍角-涡流', AgentStateCheckWay.COLOR_RANGE_CONNECT,
                                            template_id='soukaku', lower_color=(0, 220, 220), upper_color=(175, 255, 255), connect_cnt=15)])

    ZHU_YUAN = Agent('zhu_yuan', '朱鸢', RareTypeEnum.S, AgentTypeEnum.ATTACK, DmgTypeEnum.ETHER, ['zhu_yuan'],
                     state_list=[AgentStateDef('朱鸢-子弹数', AgentStateCheckWay.COLOR_RANGE_CONNECT,
                                               template_id='zhu_yuan', lower_color=(240, 60, 0), upper_color=(255, 180, 20), connect_cnt=5)])

    QINGYI = Agent('qingyi', '青衣', RareTypeEnum.S, AgentTypeEnum.STUN, DmgTypeEnum.ELECTRIC, ['qingyi'],
                     state_list=[AgentStateDef('青衣-电压', AgentStateCheckWay.BACKGROUND_GRAY_RANGE_LENGTH,
                                               template_id='qingyi', lower_color=0, upper_color=70)])

    JANE_DOE = Agent('jane_doe', '简', RareTypeEnum.S, AgentTypeEnum.ANOMALY, DmgTypeEnum.PHYSICAL, ['jane_doe'],
                     state_list=[AgentStateDef('简-萨霍夫跳', AgentStateCheckWay.COLOR_RANGE_EXIST,
                                               template_id='jane_attack', lower_color=(100, 20, 20), upper_color=(255, 255, 255), connect_cnt=50),
                                 AgentStateDef('简-狂热心流', AgentStateCheckWay.FOREGROUND_COLOR_RANGE_LENGTH,
                                               template_id='jane_red', lower_color=(200, 20, 20), upper_color=(255, 255, 255), connect_cnt=10)
                                 ])

    SETH_LOWELL = Agent('seth_lowell', '赛斯', RareTypeEnum.A, AgentTypeEnum.DEFENSE, DmgTypeEnum.ELECTRIC, ['seth_lowell'],
                     state_list=[AgentStateDef('赛斯-意气', AgentStateCheckWay.BACKGROUND_GRAY_RANGE_LENGTH,
                                               template_id='seth_lowell', lower_color=0, upper_color=10)])

    CAESAR_KING = Agent('caesar_king', '凯撒', RareTypeEnum.S, AgentTypeEnum.DEFENSE, DmgTypeEnum.PHYSICAL, ['caesar_king'])

    BURNICE_WHITE = Agent('burnice_white', '柏妮思', RareTypeEnum.S, AgentTypeEnum.ANOMALY, DmgTypeEnum.FIRE, ['burnice_white'],
                          state_list=[AgentStateDef('柏妮思-燃点', AgentStateCheckWay.BACKGROUND_GRAY_RANGE_LENGTH,
                                                    'burnice_white',  lower_color=0, upper_color=70)
                                      ])

    YANAGI = Agent('yanagi', '柳', RareTypeEnum.S, AgentTypeEnum.ANOMALY, DmgTypeEnum.ELECTRIC, ['yanagi'])
    LIGHTER = Agent('lighter', '莱特', RareTypeEnum.S, AgentTypeEnum.STUN, DmgTypeEnum.FIRE, ['lighter'],
                    state_list=[AgentStateDef('莱特-士气', AgentStateCheckWay.BACKGROUND_GRAY_RANGE_LENGTH,
                                              'lighter', lower_color=0, upper_color=50)])

    ASABA_HARUMASA = Agent('asaba_harumasa', '悠真', RareTypeEnum.S, AgentTypeEnum.ATTACK, DmgTypeEnum.ELECTRIC, ['asaba_harumasa'])
    HOSHIMI_MIYABI = Agent('hoshimi_miyabi', '雅', RareTypeEnum.S, AgentTypeEnum.ANOMALY, DmgTypeEnum.ICE, ['hoshimi_miyabi'],
                           state_list=[AgentStateDef('雅-落霜', AgentStateCheckWay.COLOR_RANGE_CONNECT,'hoshimi_miyabi',
                                                     lower_color=(30, 250, 250), upper_color=(255, 255, 255), connect_cnt=5)])

    ASTRA_YAO = Agent('astra_yao', '耀嘉音', RareTypeEnum.S, AgentTypeEnum.SUPPORT, DmgTypeEnum.ETHER, ['astra_yao', 'astra_yao_chandelier'],)

    EVELYN_CHEVALIER = Agent('evelyn_chevalier', '伊芙琳', RareTypeEnum.S, AgentTypeEnum.ATTACK, DmgTypeEnum.FIRE, ['evelyn_chevalier'],
                             state_list=[
                                 AgentStateDef('伊芙琳-燎火', AgentStateCheckWay.BACKGROUND_GRAY_RANGE_LENGTH,
                                               'evelyn_chevalier_1', lower_color=0, upper_color=30),
                                 AgentStateDef('伊芙琳-燎索点', AgentStateCheckWay.COLOR_RANGE_CONNECT,
                                               'evelyn_chevalier_2', lower_color=(70, 70, 70), upper_color=(255, 255, 255),
                                               connect_cnt=5)
                             ])

    SOLDIER_0_ANBY = Agent('soldier_0_anby', '零号安比', RareTypeEnum.S, AgentTypeEnum.ATTACK, DmgTypeEnum.ELECTRIC, ['soldier_0_anby'])

    PULCHRA = Agent('pulchra', '波可娜', RareTypeEnum.A, AgentTypeEnum.STUN, DmgTypeEnum.PHYSICAL, ['pulchra'],
                    state_list=[
                        AgentStateDef('波可娜-猎步', AgentStateCheckWay.COLOR_RANGE_CONNECT,'pulchra_hunter',
                                      lower_color=(200, 120, 30), upper_color=(255, 255, 255), connect_cnt=1)
                    ])

    TRIGGER = Agent('trigger', '扳机', RareTypeEnum.S, AgentTypeEnum.STUN, DmgTypeEnum.ELECTRIC, ['trigger'],
                    state_list=[
                        AgentStateDef('扳机-绝意', AgentStateCheckWay.FOREGROUND_COLOR_RANGE_LENGTH, 'trigger',
                                      lower_color=(0, 50, 0), upper_color=(255, 255, 255))
                    ])

    VIVIAN = Agent('vivian', '薇薇安', RareTypeEnum.S, AgentTypeEnum.ANOMALY, DmgTypeEnum.ETHER, ['vivian'],
                    state_list=[
                        AgentStateDef('薇薇安-飞羽', AgentStateCheckWay.COLOR_RANGE_CONNECT,
                                    'vivian_master_1', lower_color=(150, 110, 170), upper_color=(255, 255, 255),
                                    connect_cnt=5),
                        AgentStateDef('薇薇安-护羽', AgentStateCheckWay.COLOR_RANGE_CONNECT,
                                    'vivian_master_2', lower_color=(170, 170, 200), upper_color=(255, 255, 255),
                                    connect_cnt=5)
                    ])

    HUGO_VLAD = Agent('hugo_vlad', '雨果', RareTypeEnum.S, AgentTypeEnum.ATTACK, DmgTypeEnum.ICE, ['hugo_vlad'])

    YIXUAN = Agent('yixuan', '仪玄', RareTypeEnum.S, AgentTypeEnum.RUPTURE, DmgTypeEnum.ETHER, ['yixuan', 'yixuan_trails_of_ink'],
                   state_list=[
                       AgentStateDef('仪玄-玄墨值', AgentStateCheckWay.COLOR_RANGE_CONNECT,
                                     template_id='yixuan_auric_Ink',
                                     hsv_color=(20, 127, 255), hsv_color_diff=(15, 128, 50),
                                     connect_cnt=10, min_value_trigger_state=0),
                       AgentStateDef('仪玄-术法值', AgentStateCheckWay.FOREGROUND_COLOR_RANGE_LENGTH,
                                     template_id='yixuan_technique',
                                     hsv_color=(30, 127, 255), hsv_color_diff=(20, 128, 50),
                                     max_length=120)
                   ])

    PANYINHU = Agent('panyinhu', '潘引壶', RareTypeEnum.A, AgentTypeEnum.DEFENSE, DmgTypeEnum.PHYSICAL, ['panyinhu'])

    JU_FUFU = Agent('ju_fufu', '橘福福', RareTypeEnum.S, AgentTypeEnum.STUN, DmgTypeEnum.FIRE, ['ju_fufu'],
                    state_list=[
                        AgentStateDef('威风', AgentStateCheckWay.FOREGROUND_COLOR_RANGE_LENGTH,
                                      template_id='ju_fufu',
                                      hsv_color=(248,164,67), hsv_color_diff=(100,100,30),
                                      max_length=200)
                    ])
