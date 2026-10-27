using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using Wpf.Ui.Appearance;

namespace OneDragonLauncherWpf
{
    internal static class WindowAppearance
    {
        [DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr window, int attribute, ref int value, int size);

        public static void Attach(Window window)
        {
            window.SourceInitialized += OnSourceInitialized;
        }

        private static void OnSourceInitialized(object sender, EventArgs e)
        {
            var window = (Window)sender;
            window.SourceInitialized -= OnSourceInitialized;
            // EnsureHandle can create the HWND before the visual tree is connected,
            // so resolve the source by its handle rather than FromVisual(window).
            IntPtr handle = new WindowInteropHelper(window).Handle;
            var source = HwndSource.FromHwnd(handle);

            // FluentWindow has now configured WindowChrome. Its glass frame can leave
            // the HWND transparent until WPF paints the gradient. Use an opaque clear
            // color for that interval; keep the actual window/content brushes intact.
            var solid = window.Background as SolidColorBrush;
            var gradient = window.Background as GradientBrush;
            Color background = solid != null ? solid.Color
                : gradient != null && gradient.GradientStops.Count > 0 ? gradient.GradientStops[0].Color
                : SystemColors.WindowColor;
            if (source.CompositionTarget != null)
                source.CompositionTarget.BackgroundColor = Color.FromRgb(background.R, background.G, background.B);

            // ApplicationThemeManager.Apply ran before this HWND existed. Apply the
            // native theme now, before Show, rather than deferring it until Loaded.
            int dark = ApplicationThemeManager.GetAppTheme() == ApplicationTheme.Dark ? 1 : 0;
            int result = DwmSetWindowAttribute(source.Handle, 20 /* DWMWA_USE_IMMERSIVE_DARK_MODE */, ref dark, sizeof(int));
            if (result < 0)
                result = DwmSetWindowAttribute(source.Handle, 19 /* Older Windows 10 builds */, ref dark, sizeof(int));
            // Older Windows versions may not support either attribute. The WPF theme
            // and opaque render background still work without native dark mode.
            if (result < 0) Debug.WriteLine("Native window theme is unavailable: " + result);
        }
    }
}
