using System.ComponentModel;
using System.Runtime.CompilerServices;
using OneDragonLauncherWpf.Services;

namespace OneDragonLauncherWpf.ViewModels
{
    /// <summary>
    /// 提供启动窗口的状态文本和失败标志，防止阶段倒退或覆盖错误。
    /// </summary>
    public sealed class LauncherViewModel : INotifyPropertyChanged
    {
        private string statusMessage = "正在初始化环境并启动 GUI...";
        private string stepText = "检查工作目录与 Python 环境...";
        private LaunchPhase currentPhase = LaunchPhase.Initializing;
        private bool hasFailed;
        /// <summary>
        /// 通知 WPF 绑定某个属性的值已变化。
        /// </summary>
        public event PropertyChangedEventHandler PropertyChanged;
        /// <summary>
        /// 显示当前启动阶段或失败原因的主标题。
        /// </summary>
        public string StatusMessage { get { return statusMessage; } set { statusMessage = value; Changed(); } }
        /// <summary>
        /// 显示当前步骤或失败详情。
        /// </summary>
        public string StepText { get { return stepText; } set { stepText = value; Changed(); } }
        /// <summary>
        /// 表示已进入失败状态，用于停止正常进度显示。
        /// </summary>
        public bool HasFailed { get { return hasFailed; } private set { hasFailed = value; Changed(); } }
        /// <summary>
        /// 向绑定层发送属性变化通知。
        /// </summary>
        /// <param name="property">变化的属性名，默认由调用成员名称提供。</param>
        private void Changed([CallerMemberName] string property = null) { PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(property)); }

        /// <summary>
        /// 应用新的启动阶段，忽略倒退阶段和失败后的普通状态更新。
        /// </summary>
        /// <param name="stage">从后端日志识别出的非空启动阶段。</param>
        public void Apply(LaunchStage stage)
        {
            if (HasFailed || stage.Phase < currentPhase) return;
            currentPhase = stage.Phase;
            StatusMessage = stage.Status;
            StepText = stage.Step;
        }

        /// <summary>
        /// 显示错误并锁定失败状态，防止后续日志恢复正常进度。
        /// </summary>
        /// <param name="status">失败标题。</param>
        /// <param name="detail">供用户排查的详细说明。</param>
        public void Fail(string status, string detail)
        {
            StatusMessage = status;
            StepText = detail;
            HasFailed = true;
        }

    }
}
