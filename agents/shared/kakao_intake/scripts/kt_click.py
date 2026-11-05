import ctypes, sys, time
u=ctypes.windll.user32
ctypes.windll.shcore.SetProcessDpiAwareness(2)
t,x,y=int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3])
lp=(y<<16)|x
u.PostMessageW(t,0x0200,0,lp); time.sleep(0.2)
u.PostMessageW(t,0x0201,1,lp); time.sleep(0.08)
u.PostMessageW(t,0x0202,0,lp); time.sleep(2)
