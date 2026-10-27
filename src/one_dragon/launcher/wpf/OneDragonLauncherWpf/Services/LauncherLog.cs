using System;
using System.Collections.Generic;
using System.Text;
using System.Text.RegularExpressions;

namespace OneDragonLauncherWpf.Services
{
    public sealed class LauncherLog
    {
        private readonly object gate = new object();
        private readonly Queue<KeyValuePair<long, string>> lines = new Queue<KeyValuePair<long, string>>();
        private long sequence;
        private int characters;
        private static readonly Regex Ansi = new Regex(@"\x1B(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1B]*(?:\x07|\x1B\\))", RegexOptions.Compiled);

        public static string Clean(string value) { return Ansi.Replace(value ?? "", "").Replace("\r", ""); }

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

        public string Snapshot() { long cursor = 0, first = 0; bool reset; return ReadSince(ref cursor, ref first, out reset); }
    }
}
