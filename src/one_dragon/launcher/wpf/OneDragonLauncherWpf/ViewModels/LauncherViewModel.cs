using System.ComponentModel;
using System.Runtime.CompilerServices;
using OneDragonLauncherWpf.Services;

namespace OneDragonLauncherWpf.ViewModels
{
    public sealed class LauncherViewModel : INotifyPropertyChanged
    {
        private string statusMessage = "正在初始化环境并启动 GUI...";
        private string stepText = "检查工作目录与 Python 环境...";
        private LaunchPhase currentPhase = LaunchPhase.Initializing;
        private bool hasFailed;
        public event PropertyChangedEventHandler PropertyChanged;
        public string StatusMessage { get { return statusMessage; } set { statusMessage = value; Changed(); } }
        public string StepText { get { return stepText; } set { stepText = value; Changed(); } }
        public bool HasFailed { get { return hasFailed; } private set { hasFailed = value; Changed(); } }
        private void Changed([CallerMemberName] string property = null) { PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(property)); }

        public void Apply(LaunchStage stage)
        {
            if (HasFailed || stage.Phase < currentPhase) return;
            currentPhase = stage.Phase;
            StatusMessage = stage.Status;
            StepText = stage.Step;
        }

        public void Fail(string status, string detail)
        {
            StatusMessage = status;
            StepText = detail;
            HasFailed = true;
        }

    }
}
