// Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
using System;
namespace BristluneQualification
{
    public sealed class InputSnapshot
    {
        public int pid, nativePid, foregroundPid, targetPid, hitPid;
        public long window, foreground, main, ownerRoot, hitRoot;
        public string title, targetName, targetId, targetClass;
        public bool enabled, offscreen;
        public double[] windowBounds, targetBounds, desktop;
    }
    public static class InputGuard
    {
        static bool Equal(double[] a, double[] b)
        {
            if (a == null || b == null || a.Length != 4 || b.Length != 4)
                return false;
            for (int i = 0; i < 4; i++)
                if (a[i] != b[i])
                    return false;
            return true;
        }
        public static double[] DiagnosticBounds(double[] value)
        {
            if (value == null || value.Length != 4) return null;
            foreach (double coordinate in value)
                if (double.IsNaN(coordinate) || double.IsInfinity(coordinate)) return null;
            return value;
        }
        public static bool Contains(double[] outer, double[] inner)
        {
            if (outer == null || inner == null || outer.Length != 4 || inner.Length != 4)
                return false;
            foreach (double x in outer)
                if (double.IsNaN(x) || double.IsInfinity(x))
                    return false;
            foreach (double x in inner)
                if (double.IsNaN(x) || double.IsInfinity(x))
                    return false;
            return outer[2] > 0 && outer[3] > 0 && inner[2] > 0 && inner[3] > 0 && inner[0] >= outer[0] && inner[1] >= outer[1] && inner[0] + inner[2] <= outer[0] + outer[2] && inner[1] + inner[3] <= outer[1] + outer[3];
        }
        public static void Validate(InputSnapshot s, int pid, long main, bool point)
        {
            if (s == null || pid <= 0 || main == 0 || s.pid != pid || s.nativePid != pid || s.targetPid != pid || s.foregroundPid != pid || s.main != main || s.ownerRoot != main || s.window == 0 || s.foreground != s.window || string.IsNullOrEmpty(s.title) || !s.enabled || s.offscreen || !Contains(s.desktop, s.windowBounds) || !Contains(s.windowBounds, s.targetBounds))
                throw new InvalidOperationException("Unproved process, window, foreground, target, or visible bounds");
            if (point && (s.hitPid != pid || s.hitRoot != s.window))
                throw new InvalidOperationException("Pointer hits a different native window");
        }
        public static void Stable(InputSnapshot a, InputSnapshot b, int pid, long main, bool point)
        {
            Validate(a, pid, main, point);
            Validate(b, pid, main, point);
            if (a.window != b.window || a.title != b.title || a.targetName != b.targetName || a.targetId != b.targetId || a.targetClass != b.targetClass || !Equal(a.windowBounds, b.windowBounds) || !Equal(a.targetBounds, b.targetBounds) || !Equal(a.desktop, b.desktop))
                throw new InvalidOperationException("Observed input target changed");
        }
    }
}
