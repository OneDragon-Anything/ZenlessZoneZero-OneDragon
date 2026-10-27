using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Threading.Tasks;
using System.Windows;
using OneDragonLauncherWpf.Services;
using OneDragonLauncherWpf.ViewModels;
using Wpf.Ui.Controls;

namespace OneDragonLauncherWpf
{
    public partial class MainWindow : FluentWindow
    {
        private readonly LauncherOptions options;
        private readonly LauncherLog log = new LauncherLog();
        private readonly LauncherViewModel model = new LauncherViewModel();
        private readonly TaskCompletionSource<bool> closeRequested = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        private PythonRunner runner;
        private TerminalWindow terminal;
        private bool busy;
        private bool dismissed;
        private bool ready;
        private bool started;
        private bool startupProblem;

        public MainWindow() : this(LauncherOptions.Parse(new[] { "--preview" })) { }

        public MainWindow(LauncherOptions options)
        {
            this.options = options;
            InitializeComponent();
            WindowAppearance.Attach(this);
            DataContext = model;
            Loaded += OnLoaded;
        }

        private async void OnLoaded(object sender, RoutedEventArgs e)
        {
            if (started) return;
            started = true;
            if (options.Preview)
            {
                model.Apply(LaunchStage.FromLog("正在检查代码更新"));
                log.Write("[界面预览] 此模式不会请求管理员权限或启动 Python。");
                log.Write("识别到虚拟环境 Python: <项目目录>\\.venv\\Scripts\\python.exe");
                log.Write("使用 Python 启动器: one_dragon.devtools.python_launcher");
                log.Write("当前工作目录: <项目目录>");
                log.Write("目录核验通过");
                log.Write("开始配置环境变量");
                log.Write("PYTHONUTF8=1 / PYTHONIOENCODING=utf-8");
                log.Write("正在检查代码更新");
                log.Write("同步代码仓库...");
                log.Write("[界面预览] 可选择、复制日志，关闭后可重新打开。");
                return;
            }
            busy = true;
            try
            {
                log.Write("检查工作目录与 Python 环境...");
                var environment = await Task.Run(() => LaunchEnvironment.Resolve(options.ProjectDirectory, AppDomain.CurrentDomain.BaseDirectory, Environment.CurrentDirectory));
                if (dismissed) return;
                if (!WindowsIntegration.IsAdministrator())
                {
                    model.StatusMessage = "正在请求管理员权限...";
                    log.Write("检测到非管理员权限，正在请求 UAC 提权...");
                    using (var elevated = WindowsIntegration.RelaunchElevated(((App)Application.Current).OriginalArguments))
                    {
                        if (elevated == null) throw new InvalidOperationException("无法启动管理员进程。");
                    }
                    dismissed = true;
                    return;
                }
                runner = new PythonRunner(log);
                runner.StageChanged += stage => Dispatch(() => { if (!ready && !dismissed) model.Apply(stage); });
                runner.ErrorDetected += () => Dispatch(() =>
                {
                    if (!dismissed && !ready) { startupProblem = true; OpenLog(); }
                });
                runner.Start(environment, options);
                await WatchStartupAsync();
                if (dismissed || (ready && !startupProblem)) return;
                await Task.WhenAny(runner.Completion, closeRequested.Task);
                if (dismissed) return;
                int exitCode = await runner.Completion;
                if (!dismissed && exitCode != 0) ShowFailure("Python 启动失败", "Python 退出码: " + exitCode + "，请查看日志。");
                else if (!ready && !dismissed) ShowFailure("主程序尚未就绪", "Python 已退出，未检测到主界面，请查看日志。");
            }
            catch (Exception exception)
            {
                string message = exception is Win32Exception && ((Win32Exception)exception).NativeErrorCode == 1223
                    ? "已取消管理员授权，未启动 Python。" : exception.Message;
                if (!dismissed) ShowFailure("启动失败", message);
            }
            finally
            {
                busy = false;
                runner?.Dispose();
                if (dismissed) Application.Current.Shutdown();
            }
        }

        private async Task WatchStartupAsync()
        {
            var family = new HashSet<uint> { (uint)runner.ProcessId };
            var timer = Stopwatch.StartNew();
            bool timeoutReported = false;
            while (!dismissed)
            {
                bool found = await Task.Run(() => WindowsIntegration.HasMainWindow(family));
                if (dismissed) return;
                if (found)
                {
                    startupProblem |= runner.HasError;
                    ready = true;
                    if (startupProblem)
                    {
                        model.Fail("主界面已启动，请检查启动日志", "启动期间出现错误或等待超时，窗口保留供查看。");
                        log.Write("[窗口监视] 已检测到主界面；启动期间存在异常，保留窗口。可手动关闭，不影响 Python。");
                        OpenLog();
                        return;
                    }
                    log.Write("[窗口监视] 检测到本次启动的 OneDragon GUI，退出启动器。");
                    Close();
                    return;
                }
                if (runner.Completion.IsCompleted) return;
                if (!timeoutReported && timer.Elapsed >= TimeSpan.FromSeconds(30))
                {
                    timeoutReported = true;
                    startupProblem = true;
                    model.StatusMessage = "启动耗时较长，正在等待主界面...";
                    model.StepText = "已等待 30 秒，可查看日志了解进度";
                    log.Write("[窗口监视] 30 秒内尚未检测到主界面，将继续等待；请查看日志确认更新或环境安装进度。");
                    OpenLog();
                }
                await Task.Delay(500);
            }
        }

        private void Dispatch(Action action)
        {
            if (!Dispatcher.HasShutdownStarted) Dispatcher.BeginInvoke(action);
        }

        private void ShowFailure(string status, string detail)
        {
            ready = false;
            log.Write("[ERROR] " + detail);
            model.Fail(status, detail);
            if (!IsVisible) Show();
            OpenLog();
        }

        private void OpenLog_Click(object sender, RoutedEventArgs e) { OpenLog(); }

        private void OpenLog()
        {
            if (terminal == null)
            {
                terminal = new TerminalWindow(log) { Owner = this };
                terminal.Closed += (sender, e) => terminal = null;
            }
            terminal.Show();
            terminal.Activate();
        }

        protected override void OnClosing(CancelEventArgs e)
        {
            // Python owns the output relay, so closing WPF does not break child output.
            if (busy)
            {
                dismissed = true;
                closeRequested.TrySetResult(true);
                terminal?.Close();
            }
            base.OnClosing(e);
        }

        protected override void OnClosed(EventArgs e)
        {
            base.OnClosed(e);
            if (!busy) Application.Current.Shutdown();
        }
    }
}
