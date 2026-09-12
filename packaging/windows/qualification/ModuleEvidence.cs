// Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
namespace BristluneQualification
{
    // Read-only metadata. The existing GuiProbe.Modules acceptance gate is separate.
    public static class ModuleEvidence
    {
        static Dictionary<string, object> D(params object[] values)
        {
            var result = new Dictionary<string, object>();
            for (int i = 0; i < values.Length; i += 2) result.Add((string)values[i], values[i + 1]);
            return result;
        }
        public static Dictionary<string, object> Measure(string path)
        {
            path = Path.GetFullPath(path);
            for (string current = path; current != null; current = Path.GetDirectoryName(current))
                if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                    throw new IOException("Linked module path refused: " + path);
            var before = new FileInfo(path);
            long bytes = before.Length, stamp = before.LastWriteTimeUtc.Ticks;
            if (bytes > 2147483648L) throw new IOException("Module file exceeds observation bound");
            string hash;
            // Windows denies replacement/writing while these original bytes are read.
            using (var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (var sha = SHA256.Create())
            {
                if (file.Length != bytes) throw new IOException("Module size changed before reading");
                hash = BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
                if (file.Length != bytes) throw new IOException("Module size changed while reading");
            }
            var after = new FileInfo(path);
            if (after.Length != bytes || after.LastWriteTimeUtc.Ticks != stamp)
                throw new IOException("Module file changed during observation");
            return D("bytes", bytes, "sha256", hash);
        }
        public static Dictionary<string, object> Capture(string root, string windows, Dictionary<string, object> payload,
            Action alive, Func<string[]> enumerate)
        {
            var rows = new List<object>(); var errors = new List<string>();
            var result = D("schema", 1, "observationOnly", true, "releaseReady", false,
                "status", "incomplete", "modules", rows, "errors", errors);
            var timer = Stopwatch.StartNew(); long total = 0;
            try
            {
                alive();
                root = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar);
                windows = Path.GetFullPath(windows).TrimEnd(Path.DirectorySeparatorChar);
                var paths = enumerate();
                if (paths.Length == 0 || paths.Length > 1024) throw new IOException("Module count exceeds observation bound or is empty");
                var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                foreach (string original in paths)
                {
                    if (timer.ElapsedMilliseconds > 15000) throw new IOException("Module observation exceeded fifteen seconds");
                    if (original.Length > 4096) throw new IOException("Module path exceeds observation bound");
                    string path = Path.GetFullPath(original), relative = null, kind;
                    if (!seen.Add(path)) throw new IOException("Repeated module path: " + path);
                    if (path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                    {
                        kind = "package"; relative = "Bristlune/" + path.Substring(root.Length + 1).Replace(Path.DirectorySeparatorChar, '/');
                        if (!payload.ContainsKey(relative)) throw new IOException("Module absent from exact payload: " + relative);
                    }
                    else if (path.StartsWith(windows + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) kind = "windows";
                    else throw new IOException("Module outside package/Windows boundary: " + path);
                    var before = new FileInfo(path);
                    total = checked(total + before.Length);
                    if (total > 2147483648L) throw new IOException("Total module bytes exceed observation bound");
                    var row = Measure(path);
                    row.Add("path", path); row.Add("kind", kind);
                    if (relative != null)
                    {
                        var expected = (Dictionary<string, object>)payload[relative];
                        if ((string)row["sha256"] != (string)expected["sha256"] || (long)row["bytes"] != Convert.ToInt64(expected["bytes"]))
                            throw new IOException("Loaded package module differs: " + relative);
                        row.Add("payloadPath", relative);
                    }
                    rows.Add(row);
                }
                alive();
                if (timer.ElapsedMilliseconds > 15000) throw new IOException("Module observation exceeded fifteen seconds");
                result["status"] = "observed";
            }
            catch (Exception error)
            {
                string text = error.ToString(); errors.Add(text.Substring(0, Math.Min(4096, text.Length)));
            }
            result.Add("elapsedMilliseconds", timer.ElapsedMilliseconds);
            return result;
        }
    }
}
