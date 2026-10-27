using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace OneDragonLauncherWpf.Services
{
    public sealed class LaunchEnvironment
    {
        public string ProjectDirectory { get; private set; }
        public string SourceDirectory { get { return Path.Combine(ProjectDirectory, "src"); } }
        public string Executable { get; private set; }
        public bool UseUv { get; private set; }

        public static LaunchEnvironment Resolve(string explicitRoot, string applicationDirectory, string workingDirectory)
        {
            string root;
            if (explicitRoot != null)
            {
                root = Path.GetFullPath(explicitRoot);
                if (!IsProject(root)) throw new DirectoryNotFoundException("指定目录中没有 src\\zzz_od：" + root);
            }
            else
            {
                var candidates = new List<string>();
                var directory = new DirectoryInfo(applicationDirectory);
                for (int depth = 0; directory != null && depth < 5; depth++, directory = directory.Parent)
                {
                    candidates.Add(directory.FullName);
                    candidates.Add(Path.Combine(directory.FullName, "ZenlessZoneZero-OneDragon"));
                    candidates.Add(Path.Combine(directory.FullName, "ZenlessZoneZero-OneDragon-main"));
                }
                candidates.Add(workingDirectory);
                candidates.Add(Path.Combine(workingDirectory, "ZenlessZoneZero-OneDragon"));
                candidates.Add(Path.Combine(workingDirectory, "ZenlessZoneZero-OneDragon-main"));
                root = candidates.Distinct(StringComparer.OrdinalIgnoreCase).FirstOrDefault(IsProject);
                if (root == null) throw new DirectoryNotFoundException(
                    "未找到 Python 源码目录 src\\zzz_od。请将启动器放入一条龙项目根目录，或使用 --project \"项目路径\" 指定位置。");
            }

            var result = new LaunchEnvironment { ProjectDirectory = root };
            var roots = new[] { root, applicationDirectory }.Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
            foreach (string path in roots)
            {
                foreach (string relative in new[] { @".venv\Scripts\python.exe", @".venv\python.exe", @".install\python\python.exe" })
                {
                    string candidate = Path.Combine(path, relative);
                    if (File.Exists(candidate)) { result.Executable = candidate; return result; }
                }
            }
            foreach (string path in roots)
            {
                foreach (string relative in new[] { @".install\uv\uv.exe", @".install\uv.exe" })
                {
                    string candidate = Path.Combine(path, relative);
                    if (File.Exists(candidate)) { result.Executable = candidate; result.UseUv = true; return result; }
                }
            }
            result.Executable = FindOnPath("uv.exe");
            if (result.Executable != null) { result.UseUv = true; return result; }
            result.Executable = FindOnPath("python.exe");
            if (result.Executable == null) throw new FileNotFoundException(
                "未找到 Python 或 uv。请先安装一条龙运行环境（.venv 或 .install），或将 Python/uv 加入 PATH。");
            return result;
        }

        private static bool IsProject(string path) { return Directory.Exists(Path.Combine(path, "src", "zzz_od")); }

        private static string FindOnPath(string name)
        {
            foreach (string item in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(Path.PathSeparator))
            {
                try
                {
                    string directory = Environment.ExpandEnvironmentVariables(item.Trim().Trim('"'));
                    if (string.IsNullOrWhiteSpace(directory)) continue;
                    // Windows Store execution aliases are not a usable Python environment.
                    if (directory.IndexOf(@"\Microsoft\WindowsApps", StringComparison.OrdinalIgnoreCase) >= 0) continue;
                    string candidate = Path.Combine(directory, name);
                    if (File.Exists(candidate)) return candidate;
                }
                catch (ArgumentException) { }
                catch (NotSupportedException) { }
            }
            return null;
        }
    }
}
