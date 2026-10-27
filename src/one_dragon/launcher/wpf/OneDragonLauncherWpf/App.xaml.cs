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
    public partial class App : Application
    {
        internal static bool HasConsole { get; private set; }
        internal string[] OriginalArguments { get; private set; }

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

        private static void ShowMessage(string message, bool error)
        {
            if (HasConsole) { if (error) Console.Error.WriteLine(message); else Console.WriteLine(message); }
            else MessageBox.Show(message, "OneDragon 启动器", MessageBoxButton.OK, error ? MessageBoxImage.Error : MessageBoxImage.Information);
        }

        private void OnUserPreferenceChanged(object sender, UserPreferenceChangedEventArgs e)
        {
            if (Dispatcher.HasShutdownStarted) return;
            // Refresh only accents, preserving the selected theme (including --dark).
            Dispatcher.BeginInvoke(new Action(() =>
            {
                if (!Dispatcher.HasShutdownStarted) ApplicationAccentColorManager.ApplySystemAccent();
            }));
        }

        protected override void OnExit(ExitEventArgs e)
        {
            SystemEvents.UserPreferenceChanged -= OnUserPreferenceChanged;
            base.OnExit(e);
        }

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
