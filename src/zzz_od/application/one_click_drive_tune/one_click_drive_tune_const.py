APP_ID = "one_click_drive_tune"
APP_NAME = "一键调优"
DEFAULT_GROUP = False
NEED_NOTIFY = True

PLUGIN_DESCRIPTION = (
    "可选套装筛选（筛选/S级/套装列表 OCR）+ CV 轮廓定位驱动盘方格；"
    "评分使用 InventoryDataProcessor；不进行强化。"
)

# 与 assets/image_analysis_pipelines 下 YAML 文件名一致（不含扩展名）
CV_PIPELINE_GRID = "驱动盘方格-代理人-装备详细"
CV_PIPELINE_SUIT = "套装筛选"
