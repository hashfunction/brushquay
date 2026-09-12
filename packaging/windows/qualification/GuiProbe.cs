// Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
// Standalone normal-consumer UIA/Win32 observer. No product code is loaded here.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Automation;
using System.Windows.Forms;
namespace BristluneQualification
{
    [ComImport, Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
    class ActivationClass
    {
    }
    [ComImport, Guid("2E941141-7F97-4756-BA1D-9DECDE894A3D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface Activation
    {
        [PreserveSig] int ActivateApplication([MarshalAs(UnmanagedType.LPWStr)] string id, [MarshalAs(UnmanagedType.LPWStr)] string args, uint options, out uint pid);
        [PreserveSig] int ActivateForFile(string id, IntPtr items, string verb, out uint pid);
        [PreserveSig] int ActivateForProtocol(string id, IntPtr items, out uint pid);
    }
    public static class GuiProbe
    {
        [StructLayout(LayoutKind.Sequential)]
        struct Rect
        {
            public int L, T, R, B;
        }
        [StructLayout(LayoutKind.Sequential)]
        struct Point
        {
            public int X, Y;
        }
        [StructLayout(LayoutKind.Sequential)]
        struct Mouse
        {
            public int X, Y; public uint Data, Flags, Time; public UIntPtr Extra;
        }
        [StructLayout(LayoutKind.Sequential)]
        struct Keyboard
        {
            public ushort Key, Scan; public uint Flags, Time; public UIntPtr Extra;
        }
        [StructLayout(LayoutKind.Explicit)]
        struct Union
        {
            [FieldOffset(0)] public Mouse Mouse; [FieldOffset(0)] public Keyboard Key;
        }
        [StructLayout(LayoutKind.Sequential)]
        struct Input
        {
            public uint Type; public Union Value;
        }
        [DllImport("user32.dll")] static extern bool EnumWindows(Func<IntPtr, IntPtr, bool> callback, IntPtr state);
        [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hwnd);
        [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
        [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
        [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr hwnd, uint flags);
        [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hwnd, out Rect rect);
        [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hwnd);
        [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hwnd, int action);
        [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
        [DllImport("user32.dll")] static extern bool IsProcessDPIAware();
        [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(Point point);
        [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
        [DllImport("user32.dll")] static extern bool GetCursorPos(out Point point);
        [DllImport("user32.dll", SetLastError = true)] static extern uint SendInput(uint count, Input[] values, int size);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern int GetPackageFullName(IntPtr handle, ref uint size, StringBuilder value);
        static Process app; static IntPtr main; static OwnedJob job;
        static bool ownedProcess, assignedJob;
        static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = 16000000 };
        static readonly List<object> steps = new List<object>(); static readonly Dictionary<string, object> report = new Dictionary<string, object>();
        static string output, fixture, expectedExe, expectedPackage, expectedHash; static DateTime started;
        static Dictionary<string, object> D(params object[] p)
        {
            var d = new Dictionary<string, object>();
            for (int i = 0; i < p.Length; i += 2)
                d.Add((string)p[i], p[i + 1]);
            return d;
        }
        static string Hash(string path)
        {
            using (var f = File.OpenRead(path))
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
        static void Save(string path, object data)
        {
            using (var f = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            using (var w = new StreamWriter(f, new UTF8Encoding(false)))
                w.Write(Json.Serialize(data));
        }
        static void Alive()
        {
            if (app == null || app.HasExited || app.StartTime.ToUniversalTime() != started || !string.Equals(app.MainModule.FileName, expectedExe, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Retained installed process changed or exited");
        }
        static int Pid(IntPtr hwnd)
        {
            uint pid;
            if (hwnd == IntPtr.Zero || GetWindowThreadProcessId(hwnd, out pid) == 0)
                throw new InvalidOperationException("Missing native window PID");
            return checked((int)pid);
        }
        static long Owner(IntPtr hwnd)
        {
            var seen = new HashSet<IntPtr>();
            while (hwnd != main)
            {
                if (hwnd == IntPtr.Zero || !seen.Add(hwnd) || seen.Count > 16 || Pid(hwnd) != app.Id)
                    throw new InvalidOperationException("Window owner chain is not the retained main window");
                hwnd = GetWindow(hwnd, 4);
            }
            return main.ToInt64();
        }
        static List<AutomationElement> Windows()
        {
            Alive();
            var handles = new List<IntPtr>();
            // Ignore unrelated windows that disappear during desktop enumeration.
            // Never unwind a managed exception through EnumWindows' callback.
            EnumWindows((h, p) =>
            {
                uint pid;
                if (IsWindowVisible(h) && GetWindowThreadProcessId(h, out pid) != 0 && pid == (uint)app.Id)
                    handles.Add(h);
                return handles.Count <= 32;
            }, IntPtr.Zero);
            if (handles.Count > 32) throw new InvalidOperationException("Too many product windows");
            var list = new List<AutomationElement>();
            foreach (var handle in handles)
            {
                try { list.Add(AutomationElement.FromHandle(handle)); }
                catch (ElementNotAvailableException) { }
            }
            return list;
        }
        static AutomationElement WaitWindow(Func<AutomationElement, bool> predicate, string label)
        {
            var timer = Stopwatch.StartNew();
            while (timer.ElapsedMilliseconds < 90000)
            {
                Alive();
                var matches = new List<AutomationElement>();
                foreach (var w in Windows())
                {
                    try
                    {
                        if (predicate(w))
                            matches.Add(w);
                    }
                    catch (ElementNotAvailableException) { }
                }
                if (matches.Count > 1)
                    throw new InvalidOperationException("Ambiguous " + label);
                if (matches.Count == 1)
                    return matches[0];
                Thread.Sleep(150);
            }
            throw new TimeoutException("Window missing: " + label);
        }
        static IntPtr Handle(AutomationElement w)
        {
            var h = new IntPtr(w.Current.NativeWindowHandle);
            if (h == IntPtr.Zero)
                throw new InvalidOperationException("Native window handle absent");
            return h;
        }
        static double[] Bounds(System.Windows.Rect r)
        {
            return new[] { r.X, r.Y, r.Width, r.Height };
        }
        static double[] NativeBounds(IntPtr h)
        {
            Rect r;
            if (!GetWindowRect(h, out r))
                throw new Win32Exception();
            return new double[] { r.L, r.T, r.R - r.L, r.B - r.T };
        }
        static double[] Desktop()
        {
            var r = SystemInformation.VirtualScreen;
            return new double[] { r.X, r.Y, r.Width, r.Height };
        }
        static InputSnapshot Snapshot(AutomationElement w, AutomationElement target, bool point, int x, int y)
        {
            Alive();
            var h = Handle(w);
            var c = target.Current;
            var fg = GetForegroundWindow();
            var hit = point ? WindowFromPoint(new Point { X = x, Y = y }) : IntPtr.Zero;
            return new InputSnapshot { pid = app.Id, nativePid = Pid(h), foregroundPid = Pid(fg), targetPid = c.ProcessId, hitPid = point ? Pid(hit) : 0, window = h.ToInt64(), foreground = fg.ToInt64(), main = main.ToInt64(), ownerRoot = Owner(h), hitRoot = point ? GetAncestor(hit, 2).ToInt64() : 0, title = w.Current.Name, targetName = c.Name, targetId = c.AutomationId, targetClass = c.ClassName, enabled = c.IsEnabled, offscreen = c.IsOffscreen, windowBounds = NativeBounds(h), targetBounds = Bounds(c.BoundingRectangle), desktop = Desktop() };
        }
        static void Foreground(AutomationElement w)
        {
            Alive();
            Owner(Handle(w));
            if (!SetForegroundWindow(Handle(w)) && GetForegroundWindow() != Handle(w))
                throw new InvalidOperationException("Cannot foreground exact owned window");
            var timer = Stopwatch.StartNew();
            while (GetForegroundWindow() != Handle(w) && timer.ElapsedMilliseconds < 3000)
                Thread.Sleep(50);
            if (GetForegroundWindow() != Handle(w))
                throw new InvalidOperationException("Exact owned foreground absent");
        }
        static AutomationElement MainWindow()
        {
            var w = AutomationElement.FromHandle(main);
            if (!w.Current.Name.Contains("Bristlune") || w.Current.ClassName != "KisMainWindow")
                throw new InvalidOperationException("Main window title/class differs");
            return w;
        }
        static List<AutomationElement> FindAll(AutomationElement w, Func<AutomationElement, bool> match)
        {
            var nodes = w.FindAll(TreeScope.Descendants, Condition.TrueCondition);
            if (nodes.Count > 3000)
                throw new InvalidOperationException("UIA node bound exceeded");
            var found = new List<AutomationElement>();
            foreach (AutomationElement n in nodes)
            {
                try
                {
                    if (n.Current.ProcessId == app.Id && n.Current.IsEnabled && !n.Current.IsOffscreen && match(n))
                        found.Add(n);
                }
                catch (ElementNotAvailableException) { }
            }
            return found;
        }
        static AutomationElement Find(AutomationElement w, Func<AutomationElement, bool> match, string label)
        {
            var timer = Stopwatch.StartNew();
            while (timer.ElapsedMilliseconds < 15000)
            {
                Alive();
                var found = FindAll(w, match);
                if (found.Count > 1)
                    throw new InvalidOperationException("Ambiguous control: " + label);
                if (found.Count == 1)
                    return found[0];
                Thread.Sleep(100);
            }
            throw new TimeoutException("Control missing: " + label);
        }
        static bool Id(AutomationElement n, string id)
        {
            return n.Current.AutomationId == id || n.Current.AutomationId.EndsWith("." + id, StringComparison.Ordinal);
        }
        static void Packet(Input[] values)
        {
            if (SendInput((uint)values.Length, values, Marshal.SizeOf(typeof(Input))) != values.Length)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "SendInput did not deliver the complete owned packet");
        }
        static Input Key(ushort key, bool up)
        {
            return new Input { Type = 1, Value = new Union { Key = new Keyboard { Key = key, Flags = up ? 2u : 0u } } };
        }
        static void Chord(AutomationElement w, params ushort[] keys)
        {
            var before = Snapshot(w, w, false, 0, 0);
            InputGuard.Stable(before, Snapshot(w, w, false, 0, 0), app.Id, main.ToInt64(), false);
            var list = new List<Input>();
            foreach (var key in keys)
                list.Add(Key(key, false));
            for (int i = keys.Length - 1; i >= 0; i--)
                list.Add(Key(keys[i], true));
            var packet = list.ToArray();
            uint sent = SendInput((uint)packet.Length, packet, Marshal.SizeOf(typeof(Input)));
            if (sent != packet.Length)
            {
                int error = Marshal.GetLastWin32Error();
                var pressed = new HashSet<ushort>();
                for (int i = 0; i < Math.Min(sent, (uint)packet.Length); i++)
                {
                    var key = packet[i].Value.Key;
                    if ((key.Flags & 2) == 0) pressed.Add(key.Key); else pressed.Remove(key.Key);
                }
                // Release only keys that this incomplete packet actually pressed.
                if (pressed.Count != 0) Packet(pressed.Select(key => Key(key, true)).ToArray());
                throw new Win32Exception(error, "Owned shortcut packet was only partially delivered");
            }
        }
        static void Activate(AutomationElement w, AutomationElement control)
        {
            var before = Snapshot(w, control, false, 0, 0);
            object p;
            if (control.TryGetCurrentPattern(InvokePattern.Pattern, out p))
            {
                InputGuard.Stable(before, Snapshot(w, control, false, 0, 0), app.Id, main.ToInt64(), false);
                ((InvokePattern)p).Invoke();
                return;
            }
            var r = control.Current.BoundingRectangle;
            int x = (int)(r.X + r.Width / 2), y = (int)(r.Y + r.Height / 2);
            InputGuard.Stable(before, Snapshot(w, control, false, 0, 0), app.Id, main.ToInt64(), false);
            Click(w, control, x, y);
        }
        static void Pointer(AutomationElement w, AutomationElement target, int x, int y, uint flags)
        {
            var first = Snapshot(w, target, false, 0, 0);
            InputGuard.Validate(first, app.Id, main.ToInt64(), false);
            if (!InputGuard.Contains(first.targetBounds, new double[] { x, y, 1, 1 }))
                throw new InvalidOperationException("Pointer is outside the observed target");
            if (!SetCursorPos(x, y))
                throw new Win32Exception();
            Point actual;
            if (!GetCursorPos(out actual) || actual.X != x || actual.Y != y)
                throw new InvalidOperationException("Pointer location changed");
            var final = Snapshot(w, target, true, x, y);
            InputGuard.Stable(first, final, app.Id, main.ToInt64(), false);
            InputGuard.Validate(final, app.Id, main.ToInt64(), true);
            Packet(new[] { new Input { Type = 0, Value = new Union { Mouse = new Mouse { Flags = flags } } } });
        }
        static void Click(AutomationElement w, AutomationElement target, int x, int y)
        {
            Pointer(w, target, x, y, 2);
            try
            {
                Pointer(w, target, x, y, 4);
            }
            catch { Packet(new[] { new Input { Type = 0, Value = new Union { Mouse = new Mouse { Flags = 4 } } } }); throw; }
        }
        static void SetNumber(AutomationElement w, string id, double value)
        {
            var n = Find(w, e => Id(e, id) && e.Current.ClassName == "KisDoubleParseSpinBox", id);
            var b = Snapshot(w, n, false, 0, 0);
            InputGuard.Validate(b, app.Id, main.ToInt64(), false);
            n.SetFocus();
            InputGuard.Stable(b, Snapshot(w, n, false, 0, 0), app.Id, main.ToInt64(), false);
            object p;
            if (n.TryGetCurrentPattern(RangeValuePattern.Pattern, out p))
            {
                var r = (RangeValuePattern)p;
                if (r.Current.IsReadOnly)
                    throw new InvalidOperationException("Read-only dimension");
                r.SetValue(value);
                if (r.Current.Value != value)
                    throw new InvalidOperationException("Dimension readback differs");
            }
            else if (n.TryGetCurrentPattern(ValuePattern.Pattern, out p))
            {
                var v = (ValuePattern)p;
                v.SetValue(value.ToString(System.Globalization.CultureInfo.InvariantCulture));
                double read;
                if (!double.TryParse(v.Current.Value, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out read) || read != value)
                    throw new InvalidOperationException("Dimension readback differs");
            }
            else
                throw new InvalidOperationException("Dimension has no normal UI value pattern");
        }
        static void Button(AutomationElement w, string name)
        {
            Activate(w, Find(w, e => e.Current.ControlType == ControlType.Button && e.Current.Name.Replace("&", "") == name, name));
        }
        static void Picker(string caption, string path, bool save)
        {
            if (!Path.GetFullPath(path).StartsWith(fixture + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) || File.Exists(path) && save)
                throw new IOException("Picker target is not a new owned fixture file");
            var w = WaitWindow(e => e.Current.Name == caption && (e.Current.ClassName == "#32770" || e.Current.ClassName == "QFileDialog"), caption);
            Owner(Handle(w));
            Foreground(w);
            Observe("picker-" + Path.GetFileName(path), w, false);
            var edit = Find(w, e => e.Current.ControlType == ControlType.Edit && (Id(e, "fileNameEdit") || e.Current.AutomationId == "1001" || e.Current.Name == "File name:"), "owned file name edit");
            var b = Snapshot(w, edit, false, 0, 0);
            InputGuard.Validate(b, app.Id, main.ToInt64(), false);
            edit.SetFocus();
            InputGuard.Stable(b, Snapshot(w, edit, false, 0, 0), app.Id, main.ToInt64(), false);
            object pattern;
            if (!edit.TryGetCurrentPattern(ValuePattern.Pattern, out pattern))
                throw new InvalidOperationException("Picker filename lacks normal ValuePattern");
            var value = (ValuePattern)pattern;
            if (value.Current.IsReadOnly)
                throw new InvalidOperationException("Picker filename is read-only");
            value.SetValue(path);
            if (value.Current.Value != path)
                throw new InvalidOperationException("Picker filename readback differs");
            Button(w, save ? "Save" : "Open");
        }
        static void FileReady(string name)
        {
            var path = Path.Combine(fixture, name);
            var timer = Stopwatch.StartNew();
            while (timer.ElapsedMilliseconds < 60000)
            {
                Alive();
                if (File.Exists(path))
                {
                    try
                    {
                        using (var f = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.None))
                        {
                            if (f.Length > 0)
                                return;
                        }
                    }
                    catch (IOException) { }
                }
                Thread.Sleep(150);
            }
            throw new TimeoutException("Expected consumer file absent: " + name);
        }
        static void MainReady(string filename)
        {
            var w = WaitWindow(e => e.Current.ClassName == "KisMainWindow" && e.Current.Name.Contains("Bristlune") && e.Current.IsEnabled && (filename == null || e.Current.Name.Contains(filename)), "document main window");
            if (Handle(w) != main)
                throw new InvalidOperationException("Main window was replaced");
            Foreground(w);
        }
        static void SaveAs(string name, bool initial)
        {
            var w = MainWindow();
            Foreground(w);
            if (initial)
                Chord(w, 0x11, 0x53);
            else
                Chord(w, 0x11, 0x10, 0x53);
            Picker("Saving As", Path.Combine(fixture, name), true);
            FileReady(name);
            MainReady(name);
        }
        static void Observe(string stage, AutomationElement w, bool screenshot)
        {
            var nodes = w.FindAll(TreeScope.Descendants, Condition.TrueCondition);
            if (nodes.Count > 3000) throw new InvalidOperationException("Diagnostic UIA node bound exceeded");
            var rows = new List<object>();
            foreach (AutomationElement n in nodes)
            {
                try
                {
                    var c = n.Current; object p;
                    rows.Add(D("name", c.Name, "id", c.AutomationId, "class", c.ClassName,
                        "type", c.ControlType.ProgrammaticName, "pid", c.ProcessId,
                        "bounds", InputGuard.DiagnosticBounds(Bounds(c.BoundingRectangle)), "enabled", c.IsEnabled,
                        "offscreen", c.IsOffscreen, "invoke", n.TryGetCurrentPattern(InvokePattern.Pattern, out p)));
                }
                catch (Exception error)
                {
                    rows.Add(D("providerReadError", error.GetType().Name + ": " + error.Message));
                }
            }
            var item = D("stage", stage, "timeUtc", DateTime.UtcNow.ToString("o"), "windowTitle", w.Current.Name, "windowClass", w.Current.ClassName, "handle", Handle(w).ToInt64(), "processId", app.Id, "processStartUtc", started.ToString("o"),
                "executableSha256", expectedHash, "packageFullName", expectedPackage, "nodes", rows);
            steps.Add(item); // Keep observations even if full-window capture is refused.
            Save(Path.Combine(output, stage + "-observation.json"), item);
            if (screenshot)
            {
                var b = Snapshot(w, w, false, 0, 0);
                InputGuard.Validate(b, app.Id, main.ToInt64(), false);
                var r = b.windowBounds;
                var path = Path.Combine(output, stage + ".png");
                using (var bitmap = new Bitmap((int)r[2], (int)r[3]))
                {
                    using (var g = Graphics.FromImage(bitmap))
                        g.CopyFromScreen((int)r[0], (int)r[1], 0, 0, bitmap.Size, CopyPixelOperation.SourceCopy);
                    InputGuard.Stable(b, Snapshot(w, w, false, 0, 0), app.Id, main.ToInt64(), false);
                    using (var f = new FileStream(path, FileMode.CreateNew))
                        bitmap.Save(f, ImageFormat.Png);
                }
                var capture = D("path", path, "sha256", Hash(path), "bounds", r, "unedited", true,
                    "purpose", "installed consumer qualification", "processId", app.Id, "handle", Handle(w).ToInt64(), "executableSha256", expectedHash);
                item.Add("capture", capture);
                Save(Path.Combine(output, stage + "-capture.json"), capture);
            }
        }
        static void Modules()
        {
            Alive();
            var rows = new List<object>();
            string root = Path.GetDirectoryName(Path.GetDirectoryName(expectedExe));
            string win = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
            var input = (Dictionary<string, object>)Json.DeserializeObject(File.ReadAllText(Path.Combine(output, "probe-input.json")));
            var payload = (Dictionary<string, object>)input["payload"];
            bool core = false, platform = false;
            foreach (ProcessModule m in app.Modules)
            {
                string path = m.FileName;
                if (path.StartsWith(root + "\\", StringComparison.OrdinalIgnoreCase))
                {
                    string rel = "Bristlune/" + path.Substring(root.Length + 1).Replace('\\', '/');
                    object entry;
                    if (!payload.TryGetValue(rel, out entry))
                        throw new IOException("Loaded package module missing from exact payload: " + rel);
                    var row = (Dictionary<string, object>)entry;
                    string hash = Hash(path);
                    if (hash != (string)row["sha256"] || new FileInfo(path).Length != Convert.ToInt64(row["bytes"]))
                        throw new IOException("Loaded module changed: " + rel);
                    rows.Add(D("path", rel, "sha256", hash));
                    core |= rel.Equals("Bristlune/bin/Qt6Core.dll", StringComparison.OrdinalIgnoreCase);
                    platform |= rel.Equals("Bristlune/plugins/platforms/qwindows.dll", StringComparison.OrdinalIgnoreCase);
                }
                else if (!path.StartsWith(win + "\\", StringComparison.OrdinalIgnoreCase))
                    throw new IOException("Loaded module outside package/Windows boundary: " + path);
            }
            if (!core || !platform)
                throw new InvalidOperationException("Actual Qt core/platform modules not observed");
            report["modules"] = rows;
        }
        static void Workflow()
        {
            MainReady(null);
            Observe("01-installed-ready", MainWindow(), true);
            Chord(MainWindow(), 0x11, 0x4e);
            var create = WaitWindow(e => e.Current.ClassName == "KisOpenPane" && e.Current.Name == "Create new document", "New Image");
            Foreground(create);
            SetNumber(create, "doubleWidth", 512);
            SetNumber(create, "doubleHeight", 384);
            Observe("new-document-settings", create, true);
            Button(create, "Create");
            MainReady(null);
            SaveAs("blank.kra", true);
            string blank = Hash(Path.Combine(fixture, "blank.kra"));
            Chord(MainWindow(), 0x42);
            Chord(MainWindow(), 0x44);
            Chord(MainWindow(), 0x09);
            Chord(MainWindow(), 0x11, 0x30);
            var canvas = Find(MainWindow(), e => e.Current.ClassName == "KisQPainterCanvas" || e.Current.ClassName == "KisOpenGLCanvas2", "actual painting canvas");
            var rect = canvas.Current.BoundingRectangle;
            int cx = (int)(rect.X + rect.Width / 2), cy = (int)(rect.Y + rect.Height / 2);
            if (rect.Width < 512 || rect.Height < 384)
                throw new InvalidOperationException("Actual canvas is too small for the known image");
            Pointer(MainWindow(), canvas, cx - 140, cy, 2);
            try
            {
                for (int i = 1; i <= 28; i++)
                {
                    Pointer(MainWindow(), canvas, cx - 140 + i * 10, cy + (int)(20 * Math.Sin(i / 4.0)), 1);
                    Thread.Sleep(18);
                }
                Pointer(MainWindow(), canvas, cx + 140, cy + (int)(20 * Math.Sin(7)), 4);
            }
            catch { Packet(new[] { new Input { Type = 0, Value = new Union { Mouse = new Mouse { Flags = 4 } } } }); throw; }
            Chord(MainWindow(), 0x09);
            SaveAs("artwork.kra", false);
            if (Hash(Path.Combine(fixture, "blank.kra")) != blank)
                throw new IOException("Original blank document changed");
            Observe("02-painted-artwork", MainWindow(), true);
            Chord(MainWindow(), 0x12, 0x46);
            var menu = Find(MainWindow(), e => e.Current.ControlType == ControlType.MenuItem && e.Current.Name.Replace("&", "") == "Export...", "File Export action");
            Activate(MainWindow(), menu);
            Picker("Exporting", Path.Combine(fixture, "artwork.png"), true);
            var png = WaitWindow(e => e.Current.ClassName == "KoDialog" && FindAll(e, n => n.Current.ClassName == "KisWdgOptionsPNG").Count == 1, "PNG export options");
            Foreground(png);
            Observe("png-export-options", png, true);
            Button(png, "OK");
            FileReady("artwork.png");
            MainReady("artwork.kra");
            Chord(MainWindow(), 0x11, 0x4f);
            Picker("Open Images", Path.Combine(fixture, "artwork.png"), false);
            MainReady("artwork.png");
            SaveAs("reopened.kra", false);
            Observe("03-reopened-export", MainWindow(), true);
            Modules();
            Chord(MainWindow(), 0x11, 0x51);
            if (!app.WaitForExit(30000) || app.ExitCode != 0)
                throw new InvalidOperationException("Normal application close did not exit zero");
            if (!job.WaitEmpty(3000))
                throw new InvalidOperationException("A product child process remained after normal close");
            report["normalExitCode"] = app.ExitCode;
            report["normalClosePassed"] = true;
        }
        public static int Main(string[] args)
        {
            if (args.Length != 6)
                return 2;
            output = Path.GetFullPath(args[0]);
            fixture = Path.GetFullPath(args[1]);
            expectedExe = Path.GetFullPath(args[2]);
            expectedPackage = args[3];
            expectedHash = args[4];
            string aumid = args[5];
            bool passed = false;
            report["normalClosePassed"] = false;
            report["ownedProcessesStopped"] = false;
            report["steps"] = steps;
            try
            {
                if (IntPtr.Size != 8 || Marshal.SizeOf(typeof(Input)) != 40) throw new InvalidOperationException("Native x64 INPUT layout differs");
                SetProcessDPIAware();
                if (!IsProcessDPIAware()) throw new InvalidOperationException("Observer physical-coordinate DPI awareness was not established");
                if (Hash(expectedExe) != expectedHash)
                    throw new IOException("Installed executable differs");
                job = new OwnedJob();
                uint pid;
                int hr = ((Activation)new ActivationClass()).ActivateApplication(aumid, null, 0, out pid);
                if (hr < 0)
                    Marshal.ThrowExceptionForHR(hr);
                if (pid == 0)
                    throw new InvalidOperationException("Broker returned PID zero");
                report["activatedPid"] = pid;
                app = Process.GetProcessById(checked((int)pid));
                var handle = app.Handle;
                started = app.StartTime.ToUniversalTime();
                report["processStartUtc"] = started.ToString("o");
                report["executableSha256"] = expectedHash;
                uint size = 0;
                if (GetPackageFullName(handle, ref size, null) != 122 || size == 0 || size > 1024)
                    throw new InvalidOperationException("Package identity length unavailable");
                var value = new StringBuilder((int)size);
                if (GetPackageFullName(handle, ref size, value) != 0 || value.ToString() != expectedPackage)
                    throw new InvalidOperationException("Broker process package identity differs");
                Alive();
                ownedProcess = true;
                job.Assign(app);
                assignedJob = true;
                report["jobAssigned"] = true;
                var w = WaitWindow(e => e.Current.ClassName == "KisMainWindow" && e.Current.Name.Contains("Bristlune"), "Bristlune main window");
                main = Handle(w);
                if (GetWindow(main, 4) != IntPtr.Zero)
                    throw new InvalidOperationException("Main window unexpectedly has an owner");
                ShowWindow(main, 9);
                Foreground(w);
                Workflow();
                passed = true;
            }
            catch (Exception error)
            {
                report["error"] = error.ToString();
                try
                {
                    if (ownedProcess && app != null && !app.HasExited)
                    {
                        foreach (var w in Windows())
                        {
                            if (main != IntPtr.Zero && GetForegroundWindow() == Handle(w))
                            {
                                Observe("failure-window", w, true);
                                break;
                            }
                        }
                    }
                }
                catch (Exception diagnostic) { report["diagnosticError"] = diagnostic.Message; }
            }
            finally
            {
                try
                {
                    // Never assign or terminate an unverified broker target.
                    if (ownedProcess && app != null && !app.HasExited)
                    {
                        Alive();
                        app.Kill();
                        if (!app.WaitForExit(15000)) throw new InvalidOperationException("Exact retained process did not stop");
                        report["forcedStop"] = true;
                    }
                    bool empty = job != null && job.StopAndVerify();
                    if (job != null) job.Dispose();
                    report["ownedProcessesStopped"] = ownedProcess && assignedJob && empty && app != null && app.HasExited;
                }
                catch (Exception cleanup)
                {
                    report["cleanupError"] = cleanup.Message;
                    passed = false;
                }
                report["passed"] = passed;
                Save(Path.Combine(output, "gui-observations.json"), report);
                if (app != null) app.Dispose();
            }
            return passed ? 0 : 1;
        }
    }
}
