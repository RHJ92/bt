import ctypes, time, sys
u=ctypes.windll.user32
main=int(sys.argv[1])
if u.GetForegroundWindow()!=main:
    u.keybd_event(0x12,0,0,0); u.SetForegroundWindow(main); u.keybd_event(0x12,0,2,0); time.sleep(0.5)
if u.GetForegroundWindow()!=main: sys.exit("메인 창이 앞에 없어 중단 — Enter 안 누름")
u.keybd_event(0x0D,0,0,0); u.keybd_event(0x0D,0,2,0); time.sleep(1.5)
print("opened")
