using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;

namespace OneDragonLauncherWpf.Services
{
    public sealed class LauncherOptions
    {
        public bool Help { get; private set; }
        public bool Version { get; private set; }
        public bool OneDragon { get; private set; }
        public bool CloseGame { get; private set; }
        public ulong? ShutdownSeconds { get; private set; }
        public bool Hibernate { get; private set; }
        public bool Sleep { get; private set; }
        public string Instance { get; private set; }
        public string ProjectDirectory { get; private set; }
        public bool Preview { get; private set; }
        public bool Dark { get; private set; }

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

        private static string ReadValue(string[] args, ref int index, string value, string option)
        {
            if (value == null && index + 1 < args.Length && !args[index + 1].StartsWith("-")) value = args[++index];
            if (string.IsNullOrWhiteSpace(value)) throw new ArgumentException(option + " 缺少参数值。");
            return value;
        }

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

    public static class CommandLine
    {
        public static string Join(IEnumerable<string> arguments) { return string.Join(" ", arguments.Select(Quote)); }

        // Windows CommandLineToArgvW / CRT escaping, including trailing backslashes.
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
