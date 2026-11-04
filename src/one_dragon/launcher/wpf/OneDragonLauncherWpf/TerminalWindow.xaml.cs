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
    /// <summary>
    /// 增量显示启动日志，支持滚动查看、复制和关闭后重新打开。
    /// </summary>
    public partial class TerminalWindow : FluentWindow
    {
        private readonly LauncherLog log;
        private readonly DispatcherTimer timer;
        private long cursor;
        private long firstSequence;

        /// <summary>
        /// 初始化日志窗口并设置定时刷新、关闭清理和 Esc 快捷键。
        /// </summary>
        /// <param name="log">与启动窗口共享的内存日志缓冲。</param>
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

        /// <summary>
        /// 读取新增日志；旧记录被淘汰时重建显示，并保留用户的选择和滚动位置。
        /// </summary>
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

        /// <summary>
        /// 复制当前保留的日志；剪贴板忙时最多重试三次，并短暂显示复制结果。
        /// </summary>
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

        /// <summary>
        /// 关闭日志窗口，不影响启动流程和日志收集。
        /// </summary>
        private void CloseLog_Click(object sender, RoutedEventArgs e) { Close(); }
    }
}
