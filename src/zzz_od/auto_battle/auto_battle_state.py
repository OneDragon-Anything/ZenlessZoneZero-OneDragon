from enum import Enum


class BattleStateEnum(Enum):

    BTN_DODGE = '按键-闪避'
    BTN_SWITCH_NEXT = '按键-切换角色-下一个'
    BTN_SWITCH_PREV = '按键-切换角色-上一个'
    BTN_SWITCH_BACKUP = '按键-切换后援'
    BTN_SWITCH_NORMAL_ATTACK = '按键-普通攻击'
    BTN_SWITCH_SPECIAL_ATTACK = '按键-特殊攻击'
    BTN_ULTIMATE = '按键-终结技'
    BTN_CHAIN_LEFT = '按键-连携技-左'
    BTN_CHAIN_RIGHT = '按键-连携技-右'
    BTN_MOVE_W = '按键-移动-前'
    BTN_MOVE_S = '按键-移动-后'
    BTN_MOVE_A = '按键-移动-左'
    BTN_MOVE_D = '按键-移动-右'
    BTN_LOCK = '按键-锁定敌人'
    BTN_CHAIN_CANCEL = '按键-连携技-取消'

    STATUS_SPECIAL_READY = '按键可用-特殊攻击'
    STATUS_ULTIMATE_READY = '按键可用-终结技'
    STATUS_CHAIN_READY = '按键可用-连携技'
    STATUS_QUICK_ASSIST_READY = '按键可用-快速支援'
    STATUS_SWITCH_BACKUP_READY = '按键可用-切换后援'
