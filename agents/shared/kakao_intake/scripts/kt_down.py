import ctypes, sys, time
from ctypes import wintypes as w
u=ctypes.windll.user32
ctypes.windll.shcore.SetProcessDpiAwareness(2)
t=int(sys.argv[1]); n=int(sys.argv[2])
r=w.RECT(); u.GetWindowRect(t,ctypes.byref(r)); x,y=(r.left+r.right)//2,(r.top+r.bottom)//2
d=(-120)&0xffff
for i in range(n):
    u.PostMessageW(t,0x020A,(d<<16),(y<<16)|(x&0xffff)); time.sleep(0.05)
time.sleep(1)
