using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace OneDragonLauncherWpf.Services
{
    /// <summary>
    /// 描述目标一条龙项目及其安装器准备的本地执行环境。
    /// </summary>
    public sealed class LaunchEnvironment
    {
        /// <summary>
        /// 包含源码、配置和运行环境的目标项目根目录。
        /// </summary>
        public string ProjectDirectory { get; private set; }
        /// <summary>
        /// 目标项目的源码目录，用于设置 PYTHONPATH。
        /// </summary>
        public string SourceDirectory { get { return Path.Combine(ProjectDirectory, "src"); } }
        /// <summary>
        /// 用于执行引导代码的项目内 Python 或 uv 路径。
        /// </summary>
        public string Executable { get; private set; }
        /// <summary>
        /// 表示执行器为 uv，需要在 Python 参数前添加 uv run 参数。
        /// </summary>
        public bool UseUv { get; private set; }

        /// <summary>
        /// 定位目标项目，检查内置 uv，并选择项目内的 Python 或 uv 执行引导代码。
        /// </summary>
        /// <param name="explicitRoot">显式指定的项目根目录；为空时自动查找。</param>
        /// <param name="applicationDirectory">启动器所在目录，作为向上查找项目的起点。</param>
        /// <param name="workingDirectory">自动查找时额外检查的当前工作目录。</param>
        /// <returns>包含目标项目和本地执行器的启动环境。</returns>
        /// <exception cref="DirectoryNotFoundException">指定路径或搜索范围内没有一条龙源码。</exception>
        /// <exception cref="FileNotFoundException">目标项目缺少内置 uv，需要运行安装器修复。</exception>
        /// <remarks>不使用 PATH 回退，也不读取或改写安装器保存的 uv_path 配置。</remarks>
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

            // 后端依赖安装器准备的 uv；Python 只能用于执行引导代码，不能替代 uv。
            string uvPath = Path.Combine(root, ".install", "uv", "uv.exe");
            if (!File.Exists(uvPath)) throw new FileNotFoundException(
                "未找到项目内置 uv，运行环境不完整。请先运行一条龙安装器安装或修复环境。", uvPath);

            var result = new LaunchEnvironment { ProjectDirectory = root };
            foreach (string relative in new[] { @".venv\Scripts\python.exe", @".venv\python.exe", @".install\python\python.exe" })
            {
                string candidate = Path.Combine(root, relative);
                if (File.Exists(candidate)) { result.Executable = candidate; return result; }
            }
            result.Executable = uvPath;
            result.UseUv = true;
            return result;
        }

        /// <summary>
        /// 检查目录是否包含一条龙业务源码，不判断运行环境是否完整。
        /// </summary>
        /// <param name="path">待检查的项目根目录。</param>
        /// <returns>存在 src/zzz_od 子目录时返回真。</returns>
        private static bool IsProject(string path) { return Directory.Exists(Path.Combine(path, "src", "zzz_od")); }

    }
}
