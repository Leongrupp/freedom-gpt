"""One visible Windows app window per installation; never navigate an existing chat."""
import ctypes
from ctypes import wintypes as w
import os
import pathlib
import subprocess
import time

import psutil

TITLES={'freedom gpt','freedom gpt · ai agent'}


def normalized(path):
    return os.path.normcase(str(pathlib.Path(str(path).strip('"')).resolve()))


def profile_argument(args):
    for index,arg in enumerate(args):
        if arg.startswith('--user-data-dir='):return arg.split('=',1)[1].strip('"')
        if arg=='--user-data-dir' and index+1<len(args):return args[index+1].strip('"')
    return None


def browser_owners(root,browser):
    expected=normalized(pathlib.Path(root)/'.cache/browser');executable=normalized(browser)
    owners={}
    for process in psutil.process_iter(['pid','exe','cmdline','create_time']):
        try:
            args=process.info['cmdline'] or []
            profile=profile_argument(args)
            if not profile or normalized(profile)!=expected or not process.info['exe']:continue
            if normalized(process.info['exe'])!=executable or any(arg.startswith('--type=') for arg in args):continue
            owners[process.pid]=process.info['create_time']
        except (OSError,ValueError,psutil.Error):continue
    return owners


class Windows:
    def __init__(self):
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.callback=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
        signatures={
            'EnumWindows':([self.callback,w.LPARAM],w.BOOL),
            'IsWindowVisible':([w.HWND],w.BOOL),'IsIconic':([w.HWND],w.BOOL),
            'GetWindowThreadProcessId':([w.HWND,ctypes.POINTER(w.DWORD)],w.DWORD),
            'GetWindowTextW':([w.HWND,w.LPWSTR,ctypes.c_int],ctypes.c_int),
            'GetClassNameW':([w.HWND,w.LPWSTR,ctypes.c_int],ctypes.c_int),
            'GetForegroundWindow':([],w.HWND),'SetForegroundWindow':([w.HWND],w.BOOL),
            'ShowWindowAsync':([w.HWND,ctypes.c_int],w.BOOL),
            'BringWindowToTop':([w.HWND],w.BOOL),
            'AttachThreadInput':([w.DWORD,w.DWORD,w.BOOL],w.BOOL),
        }
        for name,(args,result) in signatures.items():
            function=getattr(self.user,name);function.argtypes=args;function.restype=result
        self.kernel.GetCurrentThreadId.argtypes=[];self.kernel.GetCurrentThreadId.restype=w.DWORD

    def windows(self,owners):
        found=[]
        def visit(hwnd,unused):
            pid=w.DWORD();self.user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value not in owners or not self.user.IsWindowVisible(hwnd):return True
            title=ctypes.create_unicode_buffer(512);kind=ctypes.create_unicode_buffer(128)
            self.user.GetWindowTextW(hwnd,title,len(title));self.user.GetClassNameW(hwnd,kind,len(kind))
            if kind.value!='Chrome_WidgetWin_1' or title.value.casefold() not in TITLES:return True
            found.append({'hwnd':int(hwnd),'pid':pid.value,'created':owners[pid.value],
                          'title':title.value,'minimized':bool(self.user.IsIconic(hwnd))})
            return True
        callback=self.callback(visit);self.user.EnumWindows(callback,0)
        return found

    def activate(self,window):
        hwnd=window['hwnd']
        if self.user.IsIconic(hwnd):self.user.ShowWindowAsync(hwnd,9)
        self.user.BringWindowToTop(hwnd);self.user.SetForegroundWindow(hwnd)
        if self.user.GetForegroundWindow()==hwnd:return True
        current=self.kernel.GetCurrentThreadId()
        foreground=self.user.GetForegroundWindow()
        target_thread=self.user.GetWindowThreadProcessId(hwnd,None)
        foreground_thread=self.user.GetWindowThreadProcessId(foreground,None) if foreground else 0
        attached=[]
        try:
            for thread in {target_thread,foreground_thread}-{0,current}:
                if self.user.AttachThreadInput(current,thread,True):attached.append(thread)
            self.user.BringWindowToTop(hwnd);self.user.SetForegroundWindow(hwnd)
        finally:
            for thread in attached:self.user.AttachThreadInput(current,thread,False)
        return self.user.GetForegroundWindow()==hwnd


def current_windows(root,browser,desktop=None):
    return (desktop or Windows()).windows(browser_owners(root,browser))


def open_or_activate(root,url,browser,desktop=None,spawn=None,timeout=12):
    from bootstrap import read,write
    root=pathlib.Path(root);desktop=desktop or Windows()
    record=root/'.tmp/app-window.json'
    windows=current_windows(root,browser,desktop)
    if windows:
        # Hints never override current PID, creation time, executable and profile.
        previous=read(record,{})
        window=next((item for item in windows if all(item.get(key)==previous.get(key) for key in ['hwnd','pid','created'])),windows[0])
        focused=desktop.activate(window)
        write(record,{**window,'action':'activated','foreground':focused,'updated':time.time()})
        return 'activated'
    command=[str(browser),'--app='+url,'--user-data-dir='+str(root/'.cache/browser'),
             '--no-first-run','--no-default-browser-check','--disable-background-networking','--window-size=1480,960']
    (spawn or subprocess.Popen)(command)
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        windows=current_windows(root,browser,desktop)
        if windows:
            window=windows[0];focused=desktop.activate(window)
            write(record,{**window,'action':'opened','foreground':focused,'updated':time.time()})
            return 'opened'
        time.sleep(.1)
    # A slow browser is not permission to start another copy.
    return 'opening'
