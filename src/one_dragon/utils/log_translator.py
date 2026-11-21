import re

LOG_PATTERNS: list[tuple[str, str]] = [
    # Git service patterns
    (r"远程代码拉取成功[，,]实际代码源: (.*)", r"Remote code pulled successfully, source: \1"),
    (r"检测当前代码是否有修改", "Checking for local code modifications"),
    (r"成功切换到分支 (.*)", r"Successfully switched to branch \1"),
    (r"本地代码已是最新: (.*)", r"Local code is up to date: \1"),
    (r"核对当前仓库", "Verifying current repository"),
    (r"拉取远程代码\.\.\.", "Pulling remote code..."),
    (r"尝试代码源: (.*)", r"Attempting repository source: \1"),
    (r"启动 Git fetch worker: (.*)", r"Started Git fetch worker: \1"),
    (r"worker 开始 Git fetch: (.*)", r"Worker started Git fetch: \1"),
    (r"Git fetch 超时设置: (.*)", r"Git fetch timeout settings: \1"),
    (r"worker Git fetch 已返回: (.*)", r"Worker Git fetch returned: \1"),
    (r"开始导入临时 Git 仓库: (.*)", r"Importing temporary Git repository: \1"),
    (r"临时 Git 仓库导入完成: (.*)", r"Temporary Git repository imported: \1"),
    (r"未开启代码自动更新，跳过", "Auto code update is off, skipped"),
    (r"本地代码更新完成", "Local code update complete"),
    (r"本地代码更新失败", "Failed to update local code"),

    # App controller & input
    (r"已启用前台模式: (.*)", r"Foreground mode enabled: \1"),
    (r"已启用后台模式: (.*)", r"Background mode enabled: \1"),
    (r"启用后台模式失败: (.*)", r"Failed to enable background mode: \1"),
    (r"复制文字到剪切板:(.*)", r"Copied text to clipboard:\1"),
    (r"复制文字到剪切板成功", "Text copied to clipboard successfully"),
    (r"粘贴文字, 查找剪切板", "Pasting text, searching clipboard"),
    (r"粘贴文字, 获取到:(.*)", r"Pasting text, retrieved:\1"),
    (r"粘贴文字, 按下 Ctrl\+V", "Pasting text, pressing Ctrl+V"),
    (r"关闭游戏成功", "Game closed successfully"),
    (r"关闭游戏失败", "Failed to close game"),
    (r"游戏窗口未就绪", "Game window not ready"),
    (r"点击非游戏窗口区域 \((.*)\)", r"Clicked outside game window area (\1)"),
    (r"已找到游戏窗口", "Game window located"),
    (r"未检测到 (.*)", r"Not detected: \1"),
    (r"指令执行出错", "Command execution error"),
    (r"未完成初始化 无法运行", "Initialization incomplete, cannot run"),
    (r"文件读取失败 将使用默认值 (.*)", r"Failed to read file, using defaults: \1"),
    (r"开始运行", "Started execution"),
    (r"停止运行", "Stopped execution"),
    (r"运行完成", "Execution completed"),
    (r"运行失败", "Execution failed"),
    (r"开始任务: (.*)", r"Starting task: \1"),
    (r"任务完成: (.*)", r"Task completed: \1"),
    (r"等待游戏画面", "Waiting for game screen"),
    (r"正在初始化 (.*)", r"Initializing: \1"),
    (r"初始化完成", "Initialization complete"),
    (r"正在执行 (.*)", r"Executing: \1"),
    (r"执行完成", "Execution completed"),
    (r"快速支援-(.*)", r"Quick Assist - \1"),
    (r"未设置游戏路径", "Game path not set"),
    (r"未找到游戏窗口", "Game window not found"),
    (r"重置成功", "Reset successfully"),
    (r"已重置记录", "Run record reset"),
    (r"终点被 \[(.*)\] 挡住 先前往它旁边的格子", r"Target blocked by [\1], moving to adjacent tile"),
    (r"终点被 \[(.*)\] 挡住 使用炸弹", r"Target blocked by [\1], using bomb"),
    (r"炸弹使用次数已达上限 炸不掉挡路的小怪 回退为战斗通过", "Bomb usage limit reached, falling back to combat"),
    (r"使用炸弹失败 回退为战斗通过 (.*)", r"Failed to use bomb, falling back to combat: \1"),
    (r"使用医疗包失败 (.*)", r"Failed to use medical pack: \1"),
    (r"已使用炸弹", "Bomb used"),
    (r"使用炸弹失败", "Failed to use bomb"),
    (r"速刷地图 (.*)", r"Speedrun map \1"),
    (r"识别到插件槽位 (.*) 个", r"Identified \1 plug-in slots"),
    (r"列表里没有 (.*) 之前的手势应该已经快速使用了", r"List has no \1, assumed quick-used by prior gesture"),
    (r"列表里没有 (.*)", r"List has no \1"),
]

KEYWORD_REPLACEMENTS: list[tuple[str, str]] = [
    ("点击", "Click"),
    ("手柄", "Gamepad"),
    ("键盘", "Keyboard"),
    ("前台模式", "Foreground Mode"),
    ("后台模式", "Background Mode"),
    ("出战", "Deploy"),
    ("重试", "Retry"),
    ("成功", "Success"),
    ("失败", "Failed"),
    ("完成", "Complete"),
    ("代理人", "Agent"),
    ("邦布", "Bangboo"),
]

def translate_log_text(text: str) -> str:
    """Translates Chinese log messages into clean English for display."""
    if not text:
        return text

    # Handle standard log format: [time] [file line] [LEVEL]: message
    match = re.match(r"^(\[.*?\]\s*\[.*?\]\s*\[.*?\]:\s*)(.*)$", text)
    if match:
        prefix, body = match.group(1), match.group(2)
        return prefix + _translate_body(body)
    else:
        return _translate_body(text)

def _translate_body(body: str) -> str:
    """翻译日志正文 依次尝试 gettext 整句翻译、正则模板替换、关键词替换"""
    # 1. Try i18n gettext lookup first if available
    try:
        from one_dragon.utils import i18_utils
        tr = i18_utils.gt(body)
        if tr != body:
            return tr
    except Exception:
        pass

    # 2. Check regex pattern matches
    for pattern, repl in LOG_PATTERNS:
        if re.search(pattern, body):
            body = re.sub(pattern, repl, body)
            break

    # 3. Apply keyword replacements
    for kw, kw_repl in KEYWORD_REPLACEMENTS:
        if kw in body:
            body = body.replace(kw, kw_repl)

    return body
