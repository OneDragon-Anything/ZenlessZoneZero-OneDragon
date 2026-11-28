using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;

namespace OneDragonLauncherWpf.Services
{
    /// <summary>
    /// 解析并保存启动器选项，校验命令行模式和电源动作的组合。
    /// </summary>
    public sealed class LauncherOptions
    {
        /// <summary>
        /// 是否显示命令行帮助后退出。
        /// </summary>
        public bool Help { get; private set; }
        /// <summary>
        /// 是否显示启动器版本后退出。
        /// </summary>
        public bool Version { get; private set; }
        /// <summary>
        /// 是否执行一条龙命令行模式。
        /// </summary>
        public bool OneDragon { get; private set; }
        /// <summary>
        /// 是否要求后端在任务完成后关闭游戏。
        /// </summary>
        public bool CloseGame { get; private set; }
        /// <summary>
        /// 任务完成后的关机延迟秒数；为空表示未请求关机。
        /// </summary>
        public ulong? ShutdownSeconds { get; private set; }
        /// <summary>
        /// 是否要求后端在任务完成后休眠。
        /// </summary>
        public bool Hibernate { get; private set; }
        /// <summary>
        /// 是否要求后端在任务完成后睡眠。
        /// </summary>
        public bool Sleep { get; private set; }
        /// <summary>
        /// 透传给后端的账号实例列表；为空时由后端选择默认实例。
        /// </summary>
        public string Instance { get; private set; }
        /// <summary>
        /// 用户显式指定的项目目录；为空时自动定位。
        /// </summary>
        public string ProjectDirectory { get; private set; }
        /// <summary>
        /// 是否仅预览界面，不提权或启动 Python。
        /// </summary>
        public bool Preview { get; private set; }
        /// <summary>
        /// 是否强制使用深色主题。
        /// </summary>
        public bool Dark { get; private set; }

        /// <summary>
        /// 帮助和参数错误提示使用的命令行说明。
        /// </summary>
        public const string Usage = @"OneDragon Launcher WPF
  -h, --help                 显示帮助
  -v, --version              显示版本
  -o, --onedragon            运行一条龙命令行模式
  -c, --close-game           完成后关闭游戏（需 --onedragon）
  -s, --shutdown [秒]        完成后关机，默认 60 秒（需 --onedragon）
      --hibernate           完成后休眠（需 --onedragon）
      --sleep               完成后睡眠（需 --onedragon）
  -i, --instance 1,2         指定账号实例（需 --onedragon）
      --project <目录>      指定含 src/zzz_od 的 Python 项目目录
      --preview             仅预览界面，不提权、不启动 Python
      --dark                使用深色主题（默认跟随系统）
关机、休眠、睡眠只能选择一种，可与 --close-game 组合。";

        /// <summary>
        /// 解析参数并校验必填值、命令行限定选项及互斥电源动作。
        /// </summary>
        /// <param name="args">不包含可执行文件名的参数数组。</param>
        /// <param name="defaultToPreview">未指定项目和命令行模式时是否默认预览，供 Debug 构建使用。</param>
        /// <returns>解析并校验后的启动选项。</returns>
        /// <exception cref="ArgumentException">参数未知、缺值或存在不允许的组合。</exception>
        public static LauncherOptions Parse(string[] args, bool defaultToPreview = false)
        {
            var result = new LauncherOptions();
            for (int i = 0; i < args.Length; i++)
            {
                string token = args[i];
                string value = null;
                int equals = token.IndexOf('=');
                if (equals >= 0) { value = token.Substring(equals + 1); token = token.Substring(0, equals); }
                if (value != null && token != "--shutdown" && token != "--instance" && token != "--project")
                    throw new ArgumentException("此参数不接受值：" + token);
                switch (token)
                {
                    case "-h": case "--help": result.Help = true; break;
                    case "-v": case "--version": result.Version = true; break;
                    case "-o": case "--onedragon": result.OneDragon = true; break;
                    case "-c": case "--close-game": result.CloseGame = true; break;
                    case "--hibernate": result.Hibernate = true; break;
                    case "--sleep": result.Sleep = true; break;
                    case "--preview": result.Preview = true; break;
                    case "--dark": result.Dark = true; break;
                    case "-i": case "--instance": result.Instance = ReadValue(args, ref i, value, token); break;
                    case "--project": result.ProjectDirectory = ReadValue(args, ref i, value, token); break;
                    case "-s": case "--shutdown":
                        if (value == null && i + 1 < args.Length && !args[i + 1].StartsWith("-")) value = args[++i];
                        ulong seconds;
                        if (!ulong.TryParse(value ?? "60", NumberStyles.None, CultureInfo.InvariantCulture, out seconds))
                            throw new ArgumentException("--shutdown 必须为非负整数秒数。");
                        result.ShutdownSeconds = seconds;
                        break;
                    default: throw new ArgumentException("未知参数：" + token + "。使用 --help 查看帮助。");
                }
            }
            if (!result.Help && !result.Version)
            {
                if (!result.OneDragon && (result.CloseGame || result.ShutdownSeconds.HasValue || result.Hibernate || result.Sleep || result.Instance != null))
                    throw new ArgumentException("--close-game、--shutdown、--hibernate、--sleep 和 --instance 只能与 --onedragon 一起使用。");
                int powerActions = (result.ShutdownSeconds.HasValue ? 1 : 0) + (result.Hibernate ? 1 : 0) + (result.Sleep ? 1 : 0);
                if (powerActions > 1)
                    throw new ArgumentException("--shutdown、--hibernate 和 --sleep 不能同时使用，请只选择一种电源动作。");
                if (result.Preview && result.OneDragon)
                    throw new ArgumentException("--preview 不能与 --onedragon 一起使用。");
                // Debug UI development should work without a separate Python checkout.
                // An explicit project or CLI mode still opts into the real launch path.
                if (defaultToPreview && !result.OneDragon && result.ProjectDirectory == null)
                    result.Preview = true;
            }
            return result;
        }

        /// <summary>
        /// 读取等号后的值或后续参数，并推进参数索引。
        /// </summary>
        /// <param name="args">原始参数数组。</param>
        /// <param name="index">当前选项的位置；消费后续参数时递增。</param>
        /// <param name="value">已从等号后解析的值；没有等号时为空。</param>
        /// <param name="option">用于缺值错误提示的选项名。</param>
        /// <returns>非空的选项值。</returns>
        /// <exception cref="ArgumentException">没有可用的选项值。</exception>
        private static string ReadValue(string[] args, ref int index, string value, string option)
        {
            if (value == null && index + 1 < args.Length && !args[index + 1].StartsWith("-")) value = args[++index];
            if (string.IsNullOrWhiteSpace(value)) throw new ArgumentException(option + " 缺少参数值。");
            return value;
        }

        /// <summary>
        /// 生成命令行模式的后端参数，保持账号及电源选项的约定顺序。
        /// </summary>
        /// <returns>首项为 --onedragon 的参数序列，后续为需要透传的选项。</returns>
        public IEnumerable<string> GetPythonArguments()
        {
            yield return "--onedragon";
            if (Instance != null) { yield return "--instance"; yield return Instance; }
            if (CloseGame) yield return "--close-game";
            if (ShutdownSeconds.HasValue) { yield return "--shutdown"; yield return ShutdownSeconds.Value.ToString(CultureInfo.InvariantCulture); }
            if (Hibernate) yield return "--hibernate";
            if (Sleep) yield return "--sleep";
        }
    }

    /// <summary>
    /// 按 Windows 命令行规则引用参数，保留空格、引号和尾部反斜杠。
    /// </summary>
    public static class CommandLine
    {
        /// <summary>
        /// 逐个引用参数并以空格连接，构造子进程命令行。
        /// </summary>
        /// <param name="arguments">尚未引用的原始参数序列。</param>
        /// <returns>可供 Windows 子进程解析的命令行字符串。</returns>
        public static string Join(IEnumerable<string> arguments) { return string.Join(" ", arguments.Select(Quote)); }

        // Windows CommandLineToArgvW / CRT escaping, including trailing backslashes.
        /// <summary>
        /// 按 CommandLineToArgvW 和 CRT 规则引用单个参数，处理引号前及末尾的反斜杠。
        /// </summary>
        /// <param name="argument">需要完整保留的原始参数。</param>
        /// <returns>包含外层双引号和必要转义的参数。</returns>
        public static string Quote(string argument)
        {
            var result = new StringBuilder("\"");
            int slashes = 0;
            foreach (char c in argument)
            {
                if (c == '\\') { slashes++; continue; }
                result.Append('\\', c == '"' ? slashes * 2 + 1 : slashes);
                result.Append(c);
                slashes = 0;
            }
            return result.Append('\\', slashes * 2).Append('"').ToString();
        }
    }
}
