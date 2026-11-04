using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
using System.Threading.Tasks;

namespace OneDragonLauncherWpf.Services
{
    /// <summary>
    /// 封装应用标识、控制台连接、管理员重启及进程窗口监视。
    /// </summary>
    internal static class WindowsIntegration
    {
        private const string AppId = "ZenlessZoneZero-OneDragon";

        /// <summary>
        /// 设置当前进程的显式应用标识，供 Windows 任务栏归组使用。
        /// </summary>
        [DllImport("shell32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)] private static extern int SetCurrentProcessExplicitAppUserModelID(string appId);
        /// <summary>
        /// 将当前进程连接到指定进程的控制台。
        /// </summary>
        [DllImport("kernel32.dll", SetLastError = true)] private static extern bool AttachConsole(uint processId);
        /// <summary>
        /// 获取当前进程关联的控制台窗口句柄。
        /// </summary>
        [DllImport("kernel32.dll")] private static extern IntPtr GetConsoleWindow();
        /// <summary>
        /// 枚举顶层窗口，回调返回假时停止枚举。
        /// </summary>
        [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsCallback callback, IntPtr parameter);
        /// <summary>
        /// 查询窗口是否处于可见状态。
        /// </summary>
        [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr window);
        /// <summary>
        /// 将窗口标题写入调用方提供的字符缓冲。
        /// </summary>
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowText(IntPtr window, StringBuilder text, int maximum);
        /// <summary>
        /// 获取窗口所属线程，并返回拥有该窗口的进程标识。
        /// </summary>
        [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
        /// <summary>
        /// 创建系统进程快照；调用方负责关闭返回的有效句柄。
        /// </summary>
        [DllImport("kernel32.dll", SetLastError = true)] private static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint processId);
        /// <summary>
        /// 读取进程快照中的第一项，调用前需初始化结构大小。
        /// </summary>
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern bool Process32FirstW(IntPtr snapshot, ref ProcessEntry entry);
        /// <summary>
        /// 读取进程快照中的下一项，返回假表示枚举结束或失败。
        /// </summary>
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern bool Process32NextW(IntPtr snapshot, ref ProcessEntry entry);
        /// <summary>
        /// 释放进程快照等原生对象的有效句柄。
        /// </summary>
        [DllImport("kernel32.dll")] private static extern bool CloseHandle(IntPtr handle);
        /// <summary>
        /// 处理枚举到的窗口；返回真继续枚举，返回假提前停止。
        /// </summary>
        private delegate bool EnumWindowsCallback(IntPtr window, IntPtr parameter);

        /// <summary>
        /// 映射 Windows 进程快照条目，字段布局需与原生结构保持一致。
        /// </summary>
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct ProcessEntry
        {
            public uint Size, Usage, ProcessId;
            public UIntPtr DefaultHeap;
            public uint ModuleId, Threads, ParentProcessId;
            public int Priority;
            public uint Flags;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string ExeFile;
        }

        /// <summary>
        /// 设置启动器的应用标识；原生调用失败时抛出对应异常。
        /// </summary>
        public static void SetAppId()
        {
            Marshal.ThrowExceptionForHR(SetCurrentProcessExplicitAppUserModelID(AppId));
        }

        /// <summary>
        /// 尝试连接父进程控制台，并将标准输出和错误输出设置为 UTF-8。
        /// </summary>
        /// <returns>成功连接或已经存在控制台时返回真，否则返回假。</returns>
        public static bool ConnectConsole()
        {
            bool connected = AttachConsole(unchecked((uint)-1)) || GetConsoleWindow() != IntPtr.Zero;
            if (connected)
            {
                Console.OutputEncoding = Encoding.UTF8;
                Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true });
                Console.SetError(new StreamWriter(Console.OpenStandardError(), new UTF8Encoding(false)) { AutoFlush = true });
            }
            return connected;
        }

        /// <summary>
        /// 检查当前进程令牌是否具备管理员角色。
        /// </summary>
        /// <returns>当前进程以管理员身份运行时返回真。</returns>
        public static bool IsAdministrator()
        {
            using (var identity = WindowsIdentity.GetCurrent())
                return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
        }

        /// <summary>
        /// 通过 UAC 以管理员权限重新启动当前程序，保留参数和工作目录。
        /// </summary>
        /// <param name="arguments">需要传递给新启动器的原始参数。</param>
        /// <returns>新启动器的进程对象；由调用方释放。</returns>
        public static Process RelaunchElevated(string[] arguments)
        {
            return Process.Start(new ProcessStartInfo
            {
                FileName = Process.GetCurrentProcess().MainModule.FileName,
                Arguments = CommandLine.Join(arguments),
                WorkingDirectory = Environment.CurrentDirectory,
                UseShellExecute = true,
                Verb = "runas"
            });
        }

        // Track descendants too: uv and python_launcher can each spawn another Python process.
        /// <summary>
        /// 通过进程快照递归补充后代进程，覆盖 uv 和 Python 再次创建子进程的情况。
        /// </summary>
        /// <param name="family">已有进程标识集合，同时用于接收发现的后代。</param>
        /// <remarks>快照创建失败时保持集合不变；已创建的快照在枚举结束后释放。</remarks>
        public static void AddDescendants(HashSet<uint> family)
        {
            IntPtr snapshot = CreateToolhelp32Snapshot(2, 0);
            if (snapshot == new IntPtr(-1)) return;
            try
            {
                var parents = new Dictionary<uint, uint>();
                var entry = new ProcessEntry { Size = (uint)Marshal.SizeOf(typeof(ProcessEntry)) };
                if (Process32FirstW(snapshot, ref entry))
                    do { parents[entry.ProcessId] = entry.ParentProcessId; } while (Process32NextW(snapshot, ref entry));
                bool added;
                do
                {
                    added = false;
                    foreach (var pair in parents)
                        if (family.Contains(pair.Value) && family.Add(pair.Key)) added = true;
                } while (added);
            }
            finally { CloseHandle(snapshot); }
        }

        /// <summary>
        /// 检查本次启动的进程及其后代是否存在可见的一条龙主窗口。
        /// </summary>
        /// <param name="family">本次启动的进程集合，检查时会补充新发现的后代。</param>
        /// <returns>发现标题匹配且属于该进程集合的可见窗口时返回真。</returns>
        public static bool HasMainWindow(HashSet<uint> family)
        {
            AddDescendants(family);
            bool found = false;
            EnumWindows((window, parameter) =>
            {
                uint owner;
                GetWindowThreadProcessId(window, out owner);
                if (!family.Contains(owner) || !IsWindowVisible(window)) return true;
                var title = new StringBuilder(512);
                GetWindowText(window, title, title.Capacity);
                string normalized = title.ToString().Replace(" ", "");
                if (normalized.Contains("绝区零一条龙")) { found = true; return false; }
                return true;
            }, IntPtr.Zero);
            return found;
        }
    }
}
