import ctypes, sys
from ctypes import wintypes as w
from PIL import Image
u=ctypes.windll.user32; g=ctypes.windll.gdi32
try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception: pass
h=int(sys.argv[1]); out=sys.argv[2]
r=w.RECT(); u.GetWindowRect(h,ctypes.byref(r)); W,H=r.right-r.left,r.bottom-r.top
dc=u.GetWindowDC(h); m=g.CreateCompatibleDC(dc); b=g.CreateCompatibleBitmap(dc,W,H); g.SelectObject(m,b)
ok=u.PrintWindow(h,m,2)
class BI(ctypes.Structure):
    _fields_=[("s",w.DWORD),("w",w.LONG),("h",w.LONG),("p",w.WORD),("c",w.WORD),("cmp",w.DWORD),("si",w.DWORD),("x",w.LONG),("y",w.LONG),("u",w.DWORD),("i",w.DWORD)]
bi=BI(ctypes.sizeof(BI),W,-H,1,32,0,0,0,0,0,0)
buf=ctypes.create_string_buffer(W*H*4); g.GetDIBits(m,b,0,H,buf,ctypes.byref(bi),0)
Image.frombuffer("RGB",(W,H),buf,"raw","BGRX",0,1).save(out)
print("PrintWindow",ok,W,H)
