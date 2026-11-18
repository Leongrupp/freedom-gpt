"""Windows process lifetime: no orphaned CUDA worker after stop or UI crash."""
import ctypes,subprocess
from ctypes import wintypes
import psutil

class BasicLimits(ctypes.Structure):
    _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),
        ('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),
        ('ActiveProcessLimit',wintypes.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]

class IOCounters(ctypes.Structure):
    _fields_=[(name,ctypes.c_ulonglong) for name in ['ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount']]

class ExtendedLimits(ctypes.Structure):
    _fields_=[('BasicLimitInformation',BasicLimits),('IoInfo',IOCounters),('ProcessMemoryLimit',ctypes.c_size_t),
        ('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]

class WorkerJob:
    def __init__(self):
        self.api=ctypes.WinDLL('kernel32',use_last_error=True);self.handle=None
        self.api.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];self.api.CreateJobObjectW.restype=wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];self.api.SetInformationJobObject.restype=wintypes.BOOL
        self.api.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];self.api.OpenProcess.restype=wintypes.HANDLE
        self.api.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];self.api.AssignProcessToJobObject.restype=wintypes.BOOL
        self.api.TerminateJobObject.argtypes=[wintypes.HANDLE,wintypes.UINT];self.api.TerminateJobObject.restype=wintypes.BOOL
        self.api.CloseHandle.argtypes=[wintypes.HANDLE];self.api.CloseHandle.restype=wintypes.BOOL
        self.handle=self.api.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        limits=ExtendedLimits();limits.BasicLimitInformation.LimitFlags=0x2000 # KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            error=ctypes.get_last_error();self.close();raise ctypes.WinError(error)

    def assign_and_resume(self,process):
        # Popen must use CREATE_SUSPENDED so the venv launcher cannot create an
        # untracked child before it has inherited the job's lifetime.
        handle=self.api.OpenProcess(0x0101,False,process.pid)
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle,handle):raise ctypes.WinError(ctypes.get_last_error())
        finally:self.api.CloseHandle(handle)
        psutil.Process(process.pid).resume()

    def close(self):
        if self.handle:
            self.api.TerminateJobObject(self.handle,1);self.api.CloseHandle(self.handle);self.handle=None

    def __del__(self):self.close()

CREATE_SUSPENDED=0x00000004
