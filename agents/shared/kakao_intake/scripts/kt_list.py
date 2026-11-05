import ctypes, subprocess
from ctypes import wintypes as w
u=ctypes.windll.user32
pids={int(l.split('","')[1]) for l in subprocess.run(["tasklist","/fo","csv","/nh"],capture_output=True,text=True,errors="replace").stdout.splitlines() if "KakaoTalk" in l}
print("pids",pids)
def txt(h):
    b=ctypes.create_unicode_buffer(256); u.GetWindowTextW(h,b,256); return b.value
def cls(h):
    b=ctypes.create_unicode_buffer(256); u.GetClassNameW(h,b,256); return b.value
@ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
def cb(h,_):
    p=w.DWORD(); u.GetWindowThreadProcessId(h,ctypes.byref(p))
    if p.value in pids and txt(h):
        r=w.RECT(); u.GetWindowRect(h,ctypes.byref(r))
        print(h,repr(txt(h)),cls(h),"vis" if u.IsWindowVisible(h) else "hid","min" if u.IsIconic(h) else "",(r.left,r.top,r.right,r.bottom))
    return True
u.EnumWindows(cb,0)
