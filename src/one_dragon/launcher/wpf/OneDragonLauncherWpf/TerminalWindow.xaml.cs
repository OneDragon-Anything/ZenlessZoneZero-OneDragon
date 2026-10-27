using System;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Threading;
using OneDragonLauncherWpf.Services;
using Wpf.Ui.Controls;

namespace OneDragonLauncherWpf
{
    public partial class TerminalWindow : FluentWindow
    {
        private readonly LauncherLog log;
        private readonly DispatcherTimer timer;
        private long cursor;
        private long firstSequence;

        public TerminalWindow(LauncherLog log)
        {
            this.log = log;
            InitializeComponent();
            WindowAppearance.Attach(this);
            timer = new DispatcherTimer(DispatcherPriority.Background) { Interval = TimeSpan.FromMilliseconds(150) };
            timer.Tick += (sender, args) => RefreshLog();
            Loaded += (sender, args) => { RefreshLog(); timer.Start(); };
            Closed += (sender, args) => timer.Stop();
            PreviewKeyDown += (sender, args) => { if (args.Key == Key.Escape) { Close(); args.Handled = true; } };
        }

        private void RefreshLog()
        {
            bool reset;
            string delta = log.ReadSince(ref cursor, ref firstSequence, out reset);
            if (delta.Length == 0) return;
            bool followTail = LogText.SelectionLength == 0 && LogText.VerticalOffset + LogText.ViewportHeight >= LogText.ExtentHeight - 4;
            double offset = LogText.VerticalOffset;
            if (reset) LogText.Text = delta;
            else LogText.AppendText(delta);
            if (followTail) LogText.ScrollToEnd();
            else LogText.ScrollToVerticalOffset(offset);
        }

        private async void CopyLog_Click(object sender, RoutedEventArgs e)
        {
            CopyButton.IsEnabled = false;
            string text = log.Snapshot();
            bool copied = false;
            for (int attempt = 0; attempt < 3; attempt++)
            {
                try { Clipboard.SetText(text.Length == 0 ? "暂无日志" : text); copied = true; break; }
                catch (ExternalException) { await Task.Delay(100); }
            }
            CopyButton.Content = copied ? "已复制" : "复制失败";
            await Task.Delay(1500);
            CopyButton.Content = "复制日志";
            CopyButton.IsEnabled = true;
        }

        private void CloseLog_Click(object sender, RoutedEventArgs e) { Close(); }
    }
}
