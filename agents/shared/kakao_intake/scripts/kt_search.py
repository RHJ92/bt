import ctypes, time, sys
from ctypes import wintypes as w
u=ctypes.windll.user32
class KI(ctypes.Structure):
    _fields_=[("vk",w.WORD),("scan",w.WORD),("flags",w.DWORD),("time",w.DWORD),("extra",ctypes.c_size_t)]
class MI(ctypes.Structure):
    _fields_=[("a",w.LONG),("b",w.LONG),("c",w.DWORD),("d",w.DWORD),("e",w.DWORD),("f",ctypes.c_size_t)]
class U(ctypes.Union):
    _fields_=[("k",KI),("m",MI)]
class IN(ctypes.Structure):
    _fields_=[("type",w.DWORD),("u",U)]
def send(vk=0,scan=0,flags=0):
    i=IN(1,U(k=KI(vk,scan,flags,0,0))); u.SendInput(1,ctypes.byref(i),ctypes.sizeof(IN))
def key(vk,up=False): send(vk=vk,flags=2 if up else 0)
def typ(s):
    for c in s:
        send(scan=ord(c),flags=4); send(scan=ord(c),flags=4|2); time.sleep(0.03)
main=int(sys.argv[1]); q=sys.argv[2]
u.keybd_event(0x12,0,0,0); u.SetForegroundWindow(main); u.keybd_event(0x12,0,2,0); time.sleep(0.5)
fg=u.GetForegroundWindow()
print("foreground",fg)
if fg!=main: sys.exit("메인 창이 앞에 없어 중단 — 입력 안 함")
key(0x11); key(0x46); key(0x46,True); key(0x11,True); time.sleep(0.6)
if u.GetForegroundWindow()!=main: sys.exit("포커스 바뀜 — 입력 안 함")
typ(q); time.sleep(1); print("typed")
