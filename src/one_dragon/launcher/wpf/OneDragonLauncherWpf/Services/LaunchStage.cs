namespace OneDragonLauncherWpf.Services
{
    // 按启动顺序排列，仅用于防止日志导致阶段倒退，不表示完成百分比。
    public enum LaunchPhase
    {
        Initializing,
        CheckingDirectory,
        ConfiguringEnvironment,
        SyncingCode,
        CheckingDependencies,
        StartingGui
    }

    public sealed class LaunchStage
    {
        public LaunchPhase Phase { get; private set; }
        public string Status { get; private set; }
        public string Step { get; private set; }

        public LaunchStage(LaunchPhase phase, string status, string step)
        { Phase = phase; Status = status; Step = step; }

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
