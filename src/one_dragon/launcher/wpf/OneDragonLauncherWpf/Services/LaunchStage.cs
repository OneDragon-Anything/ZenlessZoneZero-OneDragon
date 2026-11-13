namespace OneDragonLauncherWpf.Services
{
    // 按启动顺序排列，仅用于防止日志导致阶段倒退，不表示完成百分比。
    /// <summary>
    /// 按启动顺序定义阶段，用于防止状态倒退，不表示完成百分比。
    /// </summary>
    public enum LaunchPhase
    {
        /// <summary>
        /// 正在初始化启动器。
        /// </summary>
        Initializing,
        /// <summary>
        /// 正在检查项目工作目录。
        /// </summary>
        CheckingDirectory,
        /// <summary>
        /// 正在配置 Python 运行环境变量。
        /// </summary>
        ConfiguringEnvironment,
        /// <summary>
        /// 正在同步项目代码。
        /// </summary>
        SyncingCode,
        /// <summary>
        /// 正在检查或同步 Python 依赖。
        /// </summary>
        CheckingDependencies,
        /// <summary>
        /// 正在启动一条龙主界面。
        /// </summary>
        StartingGui
    }

    /// <summary>
    /// 保存从后端日志识别出的阶段及其界面提示。
    /// </summary>
    public sealed class LaunchStage
    {
        /// <summary>
        /// 阶段顺序，用于过滤滞后的日志更新。
        /// </summary>
        public LaunchPhase Phase { get; private set; }
        /// <summary>
        /// 启动窗口显示的阶段标题。
        /// </summary>
        public string Status { get; private set; }
        /// <summary>
        /// 阶段对应的简短步骤说明。
        /// </summary>
        public string Step { get; private set; }

        /// <summary>
        /// 创建包含顺序和展示文本的启动阶段。
        /// </summary>
        /// <param name="phase">启动阶段枚举值。</param>
        /// <param name="status">阶段标题。</param>
        /// <param name="step">步骤说明。</param>
        public LaunchStage(LaunchPhase phase, string status, string step)
        { Phase = phase; Status = status; Step = step; }

        /// <summary>
        /// 根据后端日志中的已知提示识别启动阶段。
        /// </summary>
        /// <param name="line">已清理控制字符的非空日志字符串。</param>
        /// <returns>匹配到的阶段；普通日志返回空值。</returns>
        public static LaunchStage FromLog(string line)
        {
            if (line.Contains("当前工作目录") || line.Contains("目录核验通过"))
                return new LaunchStage(LaunchPhase.CheckingDirectory, "正在检查工作目录...", "验证工作目录");
            if (line.Contains("开始配置环境变量"))
                return new LaunchStage(LaunchPhase.ConfiguringEnvironment, "正在配置运行环境...", "配置环境变量");
            if (line.Contains("拉取远程代码") || line.Contains("正在检查代码更新") || line.Contains("同步代码仓库"))
                return new LaunchStage(LaunchPhase.SyncingCode, "正在同步代码更新...", "Git 代码同步");
            if (line.Contains("开始检查运行环境") || line.Contains("正在同步运行依赖"))
                return new LaunchStage(LaunchPhase.CheckingDependencies, "正在检查运行依赖...", "同步 Python 运行环境");
            if (line.Contains("正在启动中") || line.Contains("等待主界面弹出"))
                return new LaunchStage(LaunchPhase.StartingGui, "正在启动主界面...", "OneDragon GUI 启动中");
            return null;
        }
    }
}
