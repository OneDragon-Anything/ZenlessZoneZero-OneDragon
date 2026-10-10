APP_ID: str = 'bagel'
APP_NAME: str = '贝果计划'
DEFAULT_GROUP: bool = True
# 排在驱动盘拆解之后、通知之前。数值越小越靠前。
PRIORITY: int = 1800
NEED_NOTIFY: bool = False
MAP_TITLE: str = '高危雅努斯幻境'
RECOMMENDED_VALUE: str = '258000'

# 距节点超过此像素按住前进；以内改为短步。电子保险箱最后一段始终碎步。
NAV_CRUISE_DISTANCE: float = 10
# 电子保险箱巷口拐点在这个距离内就切下一段。切晚了会斜穿停车位；切得太早会在巷口原地大转弯，小地图对不上。
NAV_SAFE_CORNER_DISTANCE: float = 12
# 楼角和贴墙中间路点的切段距离。
NAV_SAFE_APPROACH_DISTANCE: float = 2
# 最后接近点前提前松键，给截图延迟与停步前移留出余量；横向仍须贴墙。
NAV_SAFE_BRAKE_DISTANCE: float = 6
NAV_SAFE_BRAKE_WAIT: float = 0.5
# 朝向偏差（度）：以内不转；不超过巡航阈值时边走边转；再大则改用横移切角。
NAV_TURN_DEADBAND: float = 7
NAV_CRUISE_TURN_LIMIT: float = 45
NAV_CRUISE_TURN_CAP: float = 30
# 边走边转的最小间隔（秒）。间隔内只按住前进，避免转向还没落地又往反方向补。
NAV_CRUISE_TURN_GAP: float = 0.4
NAV_STOP_TURN_CAP: float = 90
# 短步、校准、电子保险箱最后碎步的按下时长（秒）。
NAV_FORWARD_PRESS: float = 0.2
NAV_ALIGN_PRESS: float = 0.08
NAV_SAFE_APPROACH_PRESS: float = 0.08
# 连续两帧定位小地图的平均灰度差小于此值即认为这一帧已停止重绘。入场过渡态每帧都在
# 刷新（有效像素从 2282 一路涨到 4800+，实测帧间差 17.7~31.3），稳定后差值趋近 0
# （实测 0.22~0.93）。
SPAWN_STABLE_MAX_DIFF: float = 1.0
# 需要连续多少帧都低于门槛才判定画面已收敛。加载卡顿时入场过渡期可能恰好停一两帧
# （实测出现 0.30 -> 0.93 -> 31.26 的模式），只看单帧会把仍在入场的一局误判成稳定。
SPAWN_STABLE_FRAMES: int = 2
# 首次导航位置尚未取得时，只对几何证据不足松键等待。
NAV_INITIAL_LOCATE_MISS_LIMIT: int = 5
NAV_INITIAL_LOCATE_WAIT: float = 0.3

# 寻路模式的输入次数上限。栅格距离按实测跑速 9.9 格/秒、每轮约前进 0.5 秒折算，
# 再留出转向与脱困余量；C 点到武备箱 294 步是当前最长的一段。

# 连续定位失败的容忍轮数，超过说明小地图已经跟不上角色的移动。
NAV_LOCATE_MISS_LIMIT: int = 20

# 电子保险箱完成四轮点按后等待搜索结果，点按时机按光圈状态判断。
SAFE_UNLOCK_HITS: int = 4

# 机械保险箱：要按住交互键持续几秒才开，按不够则箱子不响应。按 3 秒不够时放宽到 3.5。
MECH_HOLD_PRESS_TIME: float = 3.5

# 三种容器各自的「交互提示」区域名与「搜查面板标题」区域名。
# 写在一起是因为代码里多处要成对取值，散在各处容易只改一半。
CONTAINER_PROMPT_AREAS: dict[str, str] = {
    'box': '武备箱交互',
    'safe': '电子保险箱交互',
    'mech': '机械保险箱交互',
}
CONTAINER_TITLE_AREAS: dict[str, str] = {
    'box': '搜查容器标题',
    'safe': '电子保险箱标题',
    'mech': '机械保险箱标题',
}
# 机械保险箱没有光圈解锁，按一次交互键就是长按开箱；其余两种是点按。
CONTAINER_HOLD_TYPES: frozenset[str] = frozenset({'mech'})

# 仓库清理：default 用下面的固定组合；custom 用用户勾选。
CLEAN_MODE_DEFAULT: str = 'default'
CLEAN_MODE_CUSTOM: str = 'custom'
CLEAN_TYPES: tuple[str, ...] = ('贵重物品', '战术棱镜', '其他', '装备', '战术道具', '门禁卡')
CLEAN_QUALITIES: tuple[str, ...] = ('C', 'B', 'A', 'S', 'Z')
DEFAULT_CLEAN_TYPES: tuple[str, ...] = ('贵重物品', '战术棱镜', '其他')
DEFAULT_CLEAN_QUALITIES: tuple[str, ...] = ('C', 'B', 'A', 'S')
