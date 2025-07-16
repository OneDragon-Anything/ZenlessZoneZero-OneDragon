from one_dragon.base.config.basic_notify_config import BasicNotifyConfig


class NotifyConfig(BasicNotifyConfig):

    @property
    def app_list(self) -> dict:
        zzz_app_list = {
        'redemption_code': '兑换码',
        'random_play': '影像店营业',
        'scratch_card': '刮刮卡',
        'trigrams_collection': '卦象集录',
        'charge_plan': '体力刷本',
        'coffee': '咖啡店',
        'notorious_hunt': '恶名狩猎',
        'engagement_reward': '活跃度奖励',
        'hollow_zero': '枯萎之都',
        'lost_void': '迷失之地',
        'shiyu_defense': '式舆防卫战',
        'city_fund': '丽都城募',
        'ridu_weekly': '丽都周纪(领奖励)',
        'email': '邮件',
        'drive_disc_dismantle': '驱动盘分解',
        'life_on_line': '真拿命验收'
        }
        return self.get('app_list', zzz_app_list)
