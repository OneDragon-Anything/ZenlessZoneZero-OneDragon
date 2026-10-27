using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace OneDragonLauncherWpf.Services
{
    public sealed class PythonRunner : IDisposable
    {
        private readonly LauncherLog log;
        private Process process;
        private int reportedError;
        public event Action<LaunchStage> StageChanged;
        public event Action ErrorDetected;
        public Task<int> Completion { get; private set; }
        public int ProcessId { get { return process.Id; } }
        public bool HasError { get { return Volatile.Read(ref reportedError) != 0; } }
        private static readonly Regex ErrorPattern = new Regex(
            @"\bERROR\b|\bCRITICAL\b|Traceback \(most recent call last\)|\b\w*(?:Error|Exception):", RegexOptions.Compiled);

        // Keep the pipe readers inside the existing Python process. All descendants inherit
        // these local pipes, not the WPF pipes. After WPF exits, the readers discard output.
        public const string GuiOutputBridge = @"import os, sys, threading, atexit
if os.name == 'nt':
    import ctypes, msvcrt
    _set_std_handle = ctypes.WinDLL('kernel32', use_last_error=True).SetStdHandle
    _set_std_handle.argtypes = [ctypes.c_ulong, ctypes.c_void_p]
    _set_std_handle.restype = ctypes.c_int
def _publish_handle(fd):
    if os.name == 'nt' and not _set_std_handle(ctypes.c_ulong(-10 - fd), msvcrt.get_osfhandle(fd)):
        raise ctypes.WinError(ctypes.get_last_error())
def _relay_output(source, target):
    try:
        while True:
            data = os.read(source, 8192)
            if not data:
                break
            if target is not None:
                try:
                    while data:
                        data = data[os.write(target, data):]
                except OSError:
                    os.close(target)
                    target = None
    finally:
        os.close(source)
        if target is not None:
            os.close(target)
_output_threads = []
for _fd in (1, 2):
    _target = os.dup(_fd)
    _source, _writer = os.pipe()
    os.dup2(_writer, _fd)
    os.close(_writer)
    _publish_handle(_fd)
    _thread = threading.Thread(target=_relay_output, args=(_source, _target), daemon=True)
    _thread.start()
    _output_threads.append(_thread)
def _finish_output():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (OSError, ValueError):
            pass
    # NUL is a device, not a disk file. Release local writers and drain the final output.
    with open(os.devnull, 'wb') as sink:
        for fd in (1, 2):
            os.dup2(sink.fileno(), fd)
            _publish_handle(fd)
    for thread in _output_threads:
        thread.join(timeout=2)
atexit.register(_finish_output)
";

        // Both entry points need this before importing the Python launcher.
        // Only shim colorama when it is actually absent.
        public const string ColoramaBootstrap = @"import sys, types
try:
    import colorama
except ModuleNotFoundError as exc:
    if exc.name != 'colorama':
        raise
    class _UniversalDummy:
        def __getattr__(self, name): return self
        def __call__(self, *a, **k): return self
        def __str__(self): return ''
        def __repr__(self): return ''
        def __add__(self, other): return str(other) if isinstance(other, str) else ''
        def __radd__(self, other): return str(other) if isinstance(other, str) else ''
    d = _UniversalDummy()
    m = types.ModuleType('colorama')
    m.__getattr__ = lambda name: d
    for name in ['colorama', 'colorama.ansi', 'colorama.ansitowin32', 'colorama.win32', 'colorama.initialise']:
        sys.modules[name] = m
";

        public const string GuiBootstrap = GuiOutputBridge + ColoramaBootstrap + @"
from one_dragon.devtools.python_launcher import run_python
run_python(['zzz_od', 'gui', 'app'], piped=True)
";

        // WPF already validates arguments and elevates, so skip the pyuac EXE wrapper.
        // GetPythonArguments always places the launcher-only --onedragon flag first.
        public const string CliBootstrap = ColoramaBootstrap + @"from one_dragon.devtools.python_launcher import run_python
run_python(['zzz_od', 'application', 'zzz_application_launcher'], no_windows=False, args=sys.argv[2:], piped=True)
";

        public PythonRunner(LauncherLog log) { this.log = log; }

        public static ProcessStartInfo CreateStartInfo(LaunchEnvironment environment, LauncherOptions options)
        {
            var args = new List<string>();
            if (environment.UseUv) args.AddRange(new[] { "run", "--frozen", "python" });
            args.Add("-u");
            if (options.OneDragon)
            {
                args.AddRange(new[] { "-c", CliBootstrap });
                args.AddRange(options.GetPythonArguments());
            }
            else args.AddRange(new[] { "-c", GuiBootstrap });
            var info = new ProcessStartInfo(environment.Executable, CommandLine.Join(args))
            {
                WorkingDirectory = environment.ProjectDirectory,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                RedirectStandardInput = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8
            };
            string inheritedPath = Environment.GetEnvironmentVariable("PYTHONPATH");
            info.EnvironmentVariables["PYTHONPATH"] = environment.SourceDirectory +
                (string.IsNullOrEmpty(inheritedPath) ? "" : ";" + inheritedPath);
            info.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
            info.EnvironmentVariables["PYTHONUTF8"] = "1";
            info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            return info;
        }

        public void Start(LaunchEnvironment environment, LauncherOptions options)
        {
            log.Write("项目目录: " + environment.ProjectDirectory);
            log.Write("Python 源码: " + environment.SourceDirectory);
            log.Write("使用执行器: " + environment.Executable);
            log.Write(options.OneDragon ? "启动一条龙命令行模式..." : "后台启动 Python 启动器与 GUI 界面 (piped=True)...");
            process = new Process { StartInfo = CreateStartInfo(environment, options) };
            process.OutputDataReceived += OnOutput;
            process.ErrorDataReceived += OnOutput;
            if (!process.Start()) throw new InvalidOperationException("无法创建 Python 子进程。");
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            // A GUI launcher has no console for Python input() prompts; deliver EOF instead of hanging.
            process.StandardInput.Close();
            Completion = Task.Run(() =>
            {
                // Parameterless WaitForExit also drains both asynchronous output readers.
                process.WaitForExit();
                int exitCode = process.ExitCode;
                log.Write("Python 进程已退出，退出码: " + exitCode);
                return exitCode;
            });
        }

        private void OnOutput(object sender, DataReceivedEventArgs args)
        {
            if (args.Data == null) return;
            string clean = LauncherLog.Clean(args.Data);
            log.Write(clean);
            LaunchStage stage = LaunchStage.FromLog(clean);
            if (stage != null) StageChanged?.Invoke(stage);
            if (ErrorPattern.IsMatch(clean) && Interlocked.Exchange(ref reportedError, 1) == 0) ErrorDetected?.Invoke();
        }

        public void Dispose() { process?.Dispose(); }
    }
}
