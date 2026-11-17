APP_ID = "lost_void"
APP_NAME = "迷失之地"
DEFAULT_GROUP = True
PRIORITY = 1110
NEED_NOTIFY = True

# 战线肃清 3 层 每层末尾 道中危机 → 挚交会谈 第 3 次挚交会谈之后就是终结之役 是最后一个休息区
LAST_FRIENDLY_TALK_TIMES: int = 3

# 邦布商店刷新费用依次 50 → 100 → 200 → 300 硬币 商店留硬币时 除最后一个休息区外 花 200 刷新(第 3 次)后不再刷新
STORE_MAX_REFRESH_TIMES: int = 3

# 邦布商店鸣徽最低价格 商店留硬币时 刷新后剩下的硬币少于这个数就不刷新
STORE_MIN_ARTIFACT_PRICE: int = 600

# 通用武备的派系 同派系鸣徽的分类名与派系名一致
GENERAL_GEAR_CATEGORY_LIST: tuple[str, ...] = ('终结', '异常·击破', '机敏', '绝境', '携游')
