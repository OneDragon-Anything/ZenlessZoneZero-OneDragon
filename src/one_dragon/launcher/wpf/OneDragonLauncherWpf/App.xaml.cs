using System;
using System.ComponentModel;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Media;
using Microsoft.Win32;
using OneDragonLauncherWpf.Services;
using Wpf.Ui.Appearance;

namespace OneDragonLauncherWpf
{
    /// <summary>
    /// 管理启动参数、主题、命令行运行及应用退出。
    /// </summary>
    public partial class App : Application
    {
        /// <summary>
        /// 表示是否已连接控制台，用于选择文本输出或消息框。
        /// </summary>
        internal static bool HasConsole { get; private set; }
        /// <summary>
        /// 保存原始启动参数，供管理员权限重启时原样传递。
        /// </summary>
        internal string[] OriginalArguments { get; private set; }

        /// <summary>
        /// 解析启动参数并进入帮助、版本查询、命令行或图形界面流程。
        /// </summary>
        /// <param name="e">包含进程命令行参数的启动事件。</param>
        protected override async void OnStartup(StartupEventArgs e)
        {
            WindowsIntegration.SetAppId();
            base.OnStartup(e);
            HasConsole = WindowsIntegration.ConnectConsole();
            OriginalArguments = e.Args;
            LauncherOptions options;
            try
            {
#if DEBUG
                options = LauncherOptions.Parse(e.Args, defaultToPreview: true);
#else
                options = LauncherOptions.Parse(e.Args);
#endif
            }
            catch (ArgumentException exception) { ShowMessage(exception.Message, true); Shutdown(1); return; }
            if (options.Help || options.Version)
            {
                ShowMessage(options.Help ? LauncherOptions.Usage : "OneDragon Launcher WPF v" + Assembly.GetExecutingAssembly().GetName().Version, false);
                Shutdown();
                return;
            }
            ApplyTheme(options.Dark || ApplicationThemeManager.GetSystemTheme() == SystemTheme.Dark);
            SystemEvents.UserPreferenceChanged += OnUserPreferenceChanged;
            if (options.OneDragon)
            {
                await RunCliAsync(options);
                return;
            }
            MainWindow = new MainWindow(options);
            MainWindow.Show();
        }

        /// <summary>
        /// 检查项目环境，按需提权，并以 Python 后端的退出码结束启动器。
        /// </summary>
        /// <param name="options">已完成组合校验的命令行选项。</param>
        /// <returns>在后端或提权后的启动器退出时完成的任务。</returns>
        private async Task RunCliAsync(LauncherOptions options)
        {
            var log = new LauncherLog();
            try
            {
                var environment = await Task.Run(() => LaunchEnvironment.Resolve(options.ProjectDirectory, AppDomain.CurrentDomain.BaseDirectory, Environment.CurrentDirectory));
                if (!WindowsIntegration.IsAdministrator())
                {
                    using (var elevated = WindowsIntegration.RelaunchElevated(OriginalArguments))
                    {
                        if (elevated == null) throw new InvalidOperationException("无法启动管理员进程。");
                        await Task.Run(() => elevated.WaitForExit());
                        Shutdown(elevated.ExitCode);
                    }
                    return;
                }
                using (var runner = new PythonRunner(log))
                {
                    runner.Start(environment, options);
                    Shutdown(await runner.Completion);
                }
            }
            catch (Exception exception)
            {
                ShowMessage(exception is Win32Exception && ((Win32Exception)exception).NativeErrorCode == 1223
                    ? "已取消管理员授权，未启动 Python。" : exception.Message, true);
                Shutdown(1);
            }
        }

        /// <summary>
        /// 向控制台输出消息；未连接控制台时显示消息框。
        /// </summary>
        /// <param name="message">需要显示的消息。</param>
        /// <param name="error">是否使用标准错误输出或错误图标。</param>
        private static void ShowMessage(string message, bool error)
        {
            if (HasConsole) { if (error) Console.Error.WriteLine(message); else Console.WriteLine(message); }
            else MessageBox.Show(message, "OneDragon 启动器", MessageBoxButton.OK, error ? MessageBoxImage.Error : MessageBoxImage.Information);
        }

        /// <summary>
        /// 系统个性化设置变化时，在界面线程刷新强调色并保留当前深浅色主题。
        /// </summary>
        private void OnUserPreferenceChanged(object sender, UserPreferenceChangedEventArgs e)
        {
            if (Dispatcher.HasShutdownStarted) return;
            // Refresh only accents, preserving the selected theme (including --dark).
            Dispatcher.BeginInvoke(new Action(() =>
            {
                if (!Dispatcher.HasShutdownStarted) ApplicationAccentColorManager.ApplySystemAccent();
            }));
        }

        /// <summary>
        /// 退出时解除系统设置事件订阅，避免保留应用对象。
        /// </summary>
        protected override void OnExit(ExitEventArgs e)
        {
            SystemEvents.UserPreferenceChanged -= OnUserPreferenceChanged;
            base.OnExit(e);
        }

        /// <summary>
        /// 设置 WPF UI 主题、系统强调色及启动窗口使用的画刷。
        /// </summary>
        /// <param name="dark">是否使用深色主题。</param>
        private void ApplyTheme(bool dark)
        {
            var theme = dark ? ApplicationTheme.Dark : ApplicationTheme.Light;
            Resources["LauncherTitleBarTheme"] = theme;
            ApplicationThemeManager.Apply(theme, Wpf.Ui.Controls.WindowBackdropType.None, false);
            ApplicationAccentColorManager.ApplySystemAccent();
            if (!dark) return;
            Resources["LauncherBackgroundBrush"] = new LinearGradientBrush(Color.FromRgb(32, 38, 43), Color.FromRgb(29, 35, 37), 45);
            Resources["LauncherMutedBrush"] = new SolidColorBrush(Color.FromRgb(186, 190, 197));
            Resources["LauncherLogBrush"] = new SolidColorBrush(Color.FromRgb(30, 30, 30));
            Resources["LauncherBorderBrush"] = new SolidColorBrush(Color.FromArgb(24, 255, 255, 255));
        }
    }
}
