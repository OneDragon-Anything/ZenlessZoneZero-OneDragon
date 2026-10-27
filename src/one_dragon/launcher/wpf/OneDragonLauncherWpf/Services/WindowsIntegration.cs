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
    internal static class WindowsIntegration
    {
        private const string AppId = "ZenlessZoneZero-OneDragon";

        [DllImport("shell32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)] private static extern int SetCurrentProcessExplicitAppUserModelID(string appId);
        [DllImport("kernel32.dll", SetLastError = true)] private static extern bool AttachConsole(uint processId);
        [DllImport("kernel32.dll")] private static extern IntPtr GetConsoleWindow();
        [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsCallback callback, IntPtr parameter);
        [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr window);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowText(IntPtr window, StringBuilder text, int maximum);
        [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
        [DllImport("kernel32.dll", SetLastError = true)] private static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint processId);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern bool Process32FirstW(IntPtr snapshot, ref ProcessEntry entry);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern bool Process32NextW(IntPtr snapshot, ref ProcessEntry entry);
        [DllImport("kernel32.dll")] private static extern bool CloseHandle(IntPtr handle);
        private delegate bool EnumWindowsCallback(IntPtr window, IntPtr parameter);

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

        public static void SetAppId()
        {
            Marshal.ThrowExceptionForHR(SetCurrentProcessExplicitAppUserModelID(AppId));
        }

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

        public static bool IsAdministrator()
        {
            using (var identity = WindowsIdentity.GetCurrent())
                return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
        }

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
