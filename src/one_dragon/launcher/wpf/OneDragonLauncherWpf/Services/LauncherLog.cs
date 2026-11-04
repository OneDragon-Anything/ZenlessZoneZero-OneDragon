using System;
using System.Collections.Generic;
using System.Text;
using System.Text.RegularExpressions;

namespace OneDragonLauncherWpf.Services
{
    /// <summary>
    /// 保存线程安全的有界内存日志，支持增量读取和完整快照。
    /// </summary>
    public sealed class LauncherLog
    {
        private readonly object gate = new object();
        private readonly Queue<KeyValuePair<long, string>> lines = new Queue<KeyValuePair<long, string>>();
        private long sequence;
        private int characters;
        private static readonly Regex Ansi = new Regex(@"\x1B(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1B]*(?:\x07|\x1B\\))", RegexOptions.Compiled);

        /// <summary>
        /// 去除日志中的 ANSI 控制序列和回车字符。
        /// </summary>
        /// <param name="value">原始日志文本；为空时按空字符串处理。</param>
        /// <returns>适合界面展示的纯文本。</returns>
        public static string Clean(string value) { return Ansi.Replace(value ?? "", "").Replace("\r", ""); }

        /// <summary>
        /// 清理并追加日志，截断超长行，淘汰超过一万条或一兆字符的旧记录。
        /// </summary>
        /// <param name="message">需要写入的一条原始日志。</param>
        /// <remarks>同时尝试写入控制台；控制台管道断开不影响内存记录。</remarks>
        public void Write(string message)
        {
            string clean = Clean(message);
            if (clean.Length > 32768) clean = clean.Substring(0, 32768) + "… [单行日志已截断]";
            lock (gate)
            {
                string line = clean + Environment.NewLine;
                lines.Enqueue(new KeyValuePair<long, string>(++sequence, line));
                characters += line.Length;
                while (lines.Count > 10000 || characters > 1024 * 1024) characters -= lines.Dequeue().Value.Length;
            }
            try { Console.WriteLine(clean); } catch (System.IO.IOException) { }
        }

        /// <summary>
        /// 读取游标后的日志；旧记录被淘汰时返回当前全部记录并通知调用方重建显示。
        /// </summary>
        /// <param name="cursor">上次读取的最后序号；读取后更新为当前序号。</param>
        /// <param name="firstSequence">上次读取时最早保留的序号，用于检测旧记录淘汰。</param>
        /// <param name="reset">返回是否需要用结果替换界面中的全部日志。</param>
        /// <returns>新增日志或重建显示所需的当前日志；没有更新时为空。</returns>
        public string ReadSince(ref long cursor, ref long firstSequence, out bool reset)
        {
            lock (gate)
            {
                long oldest = lines.Count == 0 ? 0 : lines.Peek().Key;
                reset = firstSequence > 0 && firstSequence != oldest;
                firstSequence = oldest;
                if (cursor == sequence) return "";
                var text = new StringBuilder();
                foreach (var line in lines) if (reset || line.Key > cursor) text.Append(line.Value);
                cursor = sequence;
                return text.ToString();
            }
        }

        /// <summary>
        /// 获取当前仍保留在内存中的全部日志。
        /// </summary>
        /// <returns>按写入顺序连接的日志文本。</returns>
        public string Snapshot() { long cursor = 0, first = 0; bool reset; return ReadSince(ref cursor, ref first, out reset); }
    }
}
