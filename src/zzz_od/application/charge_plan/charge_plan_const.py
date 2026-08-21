APP_ID = "charge_plan"
APP_NAME = "体力刷本"
DEFAULT_GROUP = True
PRIORITY = 600
NEED_NOTIFY = True

STATUS_SWITCH_TEAM = '需要切换配队'
STATUS_TEAM_EXHAUSTED = '没有后续预备编队'

S_RANK_BATTLE_TIMEOUT_SECONDS: dict[str, int] = {
    '实战模拟室': 120,
    '区域巡防': 120,
    '专业挑战室': 180,
    '恶名狩猎': 300,
}
