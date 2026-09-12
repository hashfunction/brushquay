// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 Trieflow LLC
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
namespace BristluneQualification
{
    public sealed class OwnedJob : IDisposable
    {
        private IntPtr handle;
        [StructLayout(LayoutKind.Sequential)]
        private struct BasicLimits
        {
            public long PerProcess, PerJob;
            public uint Flags;
            public UIntPtr MinWorking, MaxWorking;
            public uint ActiveProcesses;
            public UIntPtr Affinity;
            public uint Priority, Scheduling;
        }
        [StructLayout(LayoutKind.Sequential)]
        private struct IoCounters
        {
            public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
        }
        [StructLayout(LayoutKind.Sequential)]
        private struct Limits
        {
            public BasicLimits Basic;
            public IoCounters Io;
            public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
        }
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateJobObject(IntPtr attributes, string name);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref Limits info, uint size);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr handle);

        public OwnedJob()
        {
            handle = CreateJobObject(IntPtr.Zero, null);
            if (handle == IntPtr.Zero)
                throw new Win32Exception();
            var limits = new Limits();
            limits.Basic.Flags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if (!SetInformationJobObject(handle, 9, ref limits, (uint)Marshal.SizeOf(limits)))
            {
                int error = Marshal.GetLastWin32Error();
                Dispose();
                throw new Win32Exception(error);
            }
        }
        public void Assign(Process process)
        {
            if (!AssignProcessToJobObject(handle, process.Handle))
                throw new Win32Exception();
        }
        [StructLayout(LayoutKind.Sequential)]
        private struct Accounting
        {
            public long UserTime, KernelTime, PeriodUserTime, PeriodKernelTime;
            public uint PageFaults, TotalProcesses, ActiveProcesses, TerminatedProcesses;
        }
        [DllImport("kernel32.dll", SetLastError = true)] private static extern bool QueryInformationJobObject(IntPtr job, int infoClass, out Accounting value, uint size, IntPtr returned);
        [DllImport("kernel32.dll", SetLastError = true)] private static extern bool TerminateJobObject(IntPtr job, uint code);
        public bool WaitEmpty(int milliseconds)
        {
            var timer = Stopwatch.StartNew();
            do
            {
                Accounting value;
                if (!QueryInformationJobObject(handle, 1, out value, (uint)Marshal.SizeOf(typeof(Accounting)), IntPtr.Zero))
                    throw new Win32Exception();
                if (value.ActiveProcesses == 0)
                    return true;
                System.Threading.Thread.Sleep(50);
            } while (timer.ElapsedMilliseconds < milliseconds);
            return false;
        }
        public bool StopAndVerify()
        {
            if (WaitEmpty(1))
                return true;
            if (!TerminateJobObject(handle, 1))
                throw new Win32Exception();
            if (!WaitEmpty(15000))
                throw new InvalidOperationException("Owned job retained live product processes");
            return true;
        }
        public void Dispose()
        {
            if (handle != IntPtr.Zero)
            {
                if (!CloseHandle(handle))
                    throw new Win32Exception();
                handle = IntPtr.Zero;
            }
        }
    }

}
