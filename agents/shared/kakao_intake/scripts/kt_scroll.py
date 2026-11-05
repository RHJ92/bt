import ctypes, sys, time
from ctypes import wintypes as w
u=ctypes.windll.user32
try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception: pass
h=int(sys.argv[1]); n=int(sys.argv[2])
r=w.RECT(); u.GetWindowRect(h,ctypes.byref(r))
# 자식 창 나열
def cls(x):
    b=ctypes.create_unicode_buffer(256); u.GetClassNameW(x,b,256); return b.value
kids=[]
@ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
def cb(c,_):
    q=w.RECT(); u.GetWindowRect(c,ctypes.byref(q)); kids.append((c,cls(c),q.left-r.left,q.top-r.top,q.right-q.left,q.bottom-q.top)); return True
u.EnumChildWindows(h,cb,0)
print(kids)
x,y=r.left+230,r.top+400
target=next((c for c,k,l,t,W,H in kids if H>300),h)
for i in range(n):
    u.PostMessageW(target,0x020A,(120<<16),(y<<16)|(x&0xffff)); time.sleep(0.05)
time.sleep(1); print("target",target)
