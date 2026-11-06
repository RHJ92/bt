# 카톡 읽기 공용 도구 (2026-11-06) — 슬랙 담당·VS Code 세션 누구나 쓴다
# 원칙: 읽기·저장만. 메시지 입력칸(RICHEDIT50W)·전송은 절대 건드리지 않는다(이 도구엔 보내는 기능이 없음)
# 순서(사용자 승인 2026-11-06): ① 캡처(썸네일)로 어떤 서류인지 판별 → ② 숫자가 필요한 것만 원본 저장 → ③ 다른 근거와 대조
#
#   python -X utf8 agents/shared/kakao_intake/kakao.py rooms                      # 열려 있는 방 창 목록
#   python -X utf8 agents/shared/kakao_intake/kakao.py open "에이치엠"            # 방 찾아 열기 (몇 초 화면 뺏음 — 검색 결과 1개일 때만 엶)
#   python -X utf8 agents/shared/kakao_intake/kakao.py shot "에이치엠"            # 방 창 캡처 → PNG 경로 출력 (화면 안 뺏음). 이 PNG를 Read로 보고 판단
#   python -X utf8 agents/shared/kakao_intake/kakao.py scroll "에이치엠" up 5     # 위(과거)로/아래(최근)로 스크롤 (화면 안 뺏음). bottom = 맨 아래
#   python -X utf8 agents/shared/kakao_intake/kakao.py save-file "에이치엠" 106 559   # 캡처에서 본 「저장」 글자 좌표(캡처 PNG 기준) 클릭 → 받은 파일 경로
#   python -X utf8 agents/shared/kakao_intake/kakao.py save-photo "에이치엠" 200 520  # 캡처에서 본 사진 좌표 → 원본 저장 → 받은 파일 경로 (뷰어·저장 창이 잠깐 앞으로 나옴)
#
# 알게 된 것 (2026-11-06 시험)
# - 보조 모니터(배율 100%)에 있는 방 창은 클릭 좌표가 어긋나 「저장」이 안 먹음 → 저장 전에 방 창을 주 모니터로 옮긴다(앞으로 띄우지 않음)
# - 사진 원본: 더블클릭 → 사진 뷰어 → 오른쪽 아래 다운로드 → Windows 「다른 이름으로 저장」 창의 「저장」 → 문서\카카오톡 받은 파일\KakaoTalk_날짜_시각.jpg (원본 해상도)
#   우클릭 메뉴는 백그라운드 메시지로는 안 뜸. 저장 창의 파일 이름 칸은 메시지로 바꿔도 무시됨 → 기본 이름·폴더 그대로 저장
# - 받은 파일은 카톡 표시명 그대로 저장 — 같은 이름이 이미 있으면 카톡이 「(1)」을 붙임

import argparse
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes as w
from pathlib import Path

u = ctypes.windll.user32
g = ctypes.windll.gdi32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

HERE = Path(__file__).resolve().parent
SHOTS = HERE / "state" / "shots"
RECEIVED = Path.home() / "Documents" / "카카오톡 받은 파일"
WM_MOUSEMOVE, WM_LDOWN, WM_LUP, WM_LDBL, WM_WHEEL, WM_CLOSE, BM_CLICK = 0x0200, 0x0201, 0x0202, 0x0203, 0x020A, 0x0010, 0x00F5


def kakao_pids():
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, errors="replace").stdout
    return {int(l.split('","')[1]) for l in out.splitlines() if "KakaoTalk" in l}


def text(h):
    b = ctypes.create_unicode_buffer(512)
    u.GetWindowTextW(h, b, 512)
    return b.value


def get_text(h):
    """컨트롤 내부 글자(WM_GETTEXT) — 카톡 화면 이름(ChatRoomListView 등) 확인용"""
    b = ctypes.create_unicode_buffer(256)
    u.SendMessageW(h, 0x000D, 256, b)
    return b.value


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def rect(h):
    r = w.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def windows():
    """카톡 프로세스의 보이는 창 [(hwnd, 제목, 클래스)]"""
    pids, out = kakao_pids(), []

    @ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def cb(h, _):
        p = w.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value in pids and u.IsWindowVisible(h):
            out.append((h, text(h), cls(h)))
        return True
    u.EnumWindows(cb, 0)
    return out


def main_window():
    return next((h for h, t, c in windows() if t == "카카오톡" and c == "EVA_Window_Dblclk"), None)


def rooms():
    return [(h, t) for h, t, c in windows() if c == "EVA_Window_Dblclk" and t and t != "카카오톡"]


def room(query):
    hit = [(h, t) for h, t in rooms() if query.replace(" ", "") in t.replace(" ", "")]
    if not hit:
        sys.exit(f"열린 방 없음: {query} — 먼저 open")
    if len(hit) > 1:
        sys.exit("방이 여러 개: " + " / ".join(t for _, t in hit))
    return hit[0][0]


def children(h):
    out = []

    @ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def cb(c, _):
        out.append((c, cls(c)))
        return True
    u.EnumChildWindows(h, cb, 0)
    return out


def list_ctrl(h):
    return next(c for c, k in children(h) if k == "EVA_VH_ListControl_Dblclk")


def capture(h, out):
    L, T, R, B = rect(h)
    W, H = R - L, B - T
    dc = u.GetWindowDC(h)
    m = g.CreateCompatibleDC(dc)
    b = g.CreateCompatibleBitmap(dc, W, H)
    g.SelectObject(m, b)
    u.PrintWindow(h, m, 2)

    class BI(ctypes.Structure):
        _fields_ = [("s", w.DWORD), ("w", w.LONG), ("h", w.LONG), ("p", w.WORD), ("c", w.WORD), ("cmp", w.DWORD),
                    ("si", w.DWORD), ("x", w.LONG), ("y", w.LONG), ("u", w.DWORD), ("i", w.DWORD)]
    bi = BI(ctypes.sizeof(BI), W, -H, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(W * H * 4)
    g.GetDIBits(m, b, 0, H, buf, ctypes.byref(bi), 0)
    g.DeleteObject(b)
    g.DeleteDC(m)
    u.ReleaseDC(h, dc)
    from PIL import Image
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.frombuffer("RGB", (W, H), buf, "raw", "BGRX", 0, 1).save(out)
    return out


def to_main_monitor(h):
    """보조 모니터에 있으면 주 모니터로 옮김 — 앞으로 띄우지 않음(SWP_NOACTIVATE|NOZORDER|NOSIZE)"""
    L, T, R, B = rect(h)
    sw, sh = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    if 0 <= L and 0 <= T and R <= sw and B <= sh:
        return False
    u.SetWindowPos(h, 0, 60, 40, 0, 0, 0x0010 | 0x0004 | 0x0001)
    time.sleep(0.8)
    return True


def list_point(h, x, y):
    """캡처 PNG 좌표 → 대화 목록 컨트롤 좌표. 입력칸(RICHEDIT50W) 위면 거부"""
    L, T, _, _ = rect(h)
    for c, k in children(h):
        if k == "RICHEDIT50W":
            l, t, r, b = rect(c)
            if l - L <= x <= r - L and t - T - 10 <= y <= b - T:
                sys.exit("입력칸 위 좌표 — 거부")
    lc = list_ctrl(h)
    l, t, r, b = rect(lc)
    cx, cy = x - (l - L), y - (t - T)
    if not (0 <= cx < r - l and 0 <= cy < b - t):
        sys.exit("대화 목록 밖 좌표 — 거부")
    return lc, cx, cy


def new_file(before, wait=15):
    end = time.time() + wait
    while time.time() < end:
        now = {p for p in RECEIVED.glob("*") if p.is_file()}
        fresh = [p for p in now - before if not p.name.endswith((".crdownload", ".tmp"))]
        if fresh:
            time.sleep(1)
            return max(fresh, key=lambda p: p.stat().st_mtime)
        time.sleep(0.5)
    return None


def click(h, x, y):
    lp = (y << 16) | x
    u.PostMessageW(h, WM_MOUSEMOVE, 0, lp)
    time.sleep(0.2)
    u.PostMessageW(h, WM_LDOWN, 1, lp)
    time.sleep(0.08)
    u.PostMessageW(h, WM_LUP, 0, lp)


def answer_warning(room_h, old, wait=3):
    """「친구가 아닌 사용자가 보낸 파일은 안전하지 않을 수 있습니다. 다운로드 받으시겠습니까?」 (2026-11-06 첫 확인)
    업체방(이름이 「블루 & 」로 시작)이면 확인, 그 밖의 방이면 취소하고 이유를 돌려줌"""
    end = time.time() + wait
    while time.time() < end:
        time.sleep(0.3)
        for v, t, c in windows():
            if v in old or t or c != "EVA_Window_Dblclk":
                continue
            L, T, R, B = rect(v)
            if not (250 < R - L < 500 and 120 < B - T < 300):  # 경고 창 크기(약 327×189) — 광고 배너 등 제외
                continue
            vendor = text(room_h).startswith("블루 &")
            click(v, int((R - L) * (0.26 if vendor else 0.74)), (B - T) - 29)
            time.sleep(1)
            return None if vendor else "업체방이 아닌 방의 「친구 아닌 사용자 파일」 경고라 취소함 — 사람이 직접 저장"
    return None


def files_now():
    return {p for p in RECEIVED.glob("*") if p.is_file()} if RECEIVED.exists() else set()


def cmd_open(q, peek=False):
    main = main_window()
    if not main:
        sys.exit("카톡 메인 창 없음 — 카톡 실행 확인")
    if any(q.replace(" ", "") in t.replace(" ", "") for _, t in rooms()):
        print("이미 열려 있음")
        return
    was_min = u.IsIconic(main)
    u.ShowWindow(main, 9)
    time.sleep(0.5)
    u.keybd_event(0x12, 0, 0, 0)
    u.SetForegroundWindow(main)
    u.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.5)
    if u.GetForegroundWindow() != main:
        sys.exit("메인 창이 앞에 안 옴 — 입력 안 함")
    # 검색칸 = 메인 창의 Edit(약 327×29). Ctrl+F는 열기/닫기 토글이라, 안 보일 때만 누른다 (2026-11-06 — 두 번 눌러 닫혀 버린 오류)
    def search_edit():
        L, T, _, _ = rect(main)
        for c, k in children(main):
            if k == "Edit":
                l, t, r, b = rect(c)
                if r - l > 200 and 20 < b - t < 45:
                    return c
        return None
    se = search_edit()
    if not (se and u.IsWindowVisible(se)):
        # 폴더 탭(전체·안읽음·BT1…)이 생긴 뒤로 Ctrl+F가 안 먹음 → 돋보기 아이콘 클릭 (2026-11-06). 돋보기 = 창 오른쪽 끝에서 138, 위에서 70
        L, T, R, B = rect(main)
        view = next((c for c, k in children(main) if k == "EVA_Window" and u.IsWindowVisible(c)
                     and "ChatRoomListView" in get_text(c)), None)
        if view:
            vl, vt, _, _ = rect(view)
            click(view, (R - 138) - vl, (T + 70) - vt)
            time.sleep(0.8)
        se = search_edit()
    if not (se and u.IsWindowVisible(se)):
        for vk, up in ((0x11, 0), (0x46, 0), (0x46, 2), (0x11, 2)):  # Ctrl+F (옛 화면)
            u.keybd_event(vk, 0, up, 0)
        time.sleep(0.6)
        se = search_edit()
    if not (se and u.IsWindowVisible(se)):
        sys.exit("검색칸이 안 열림 — 입력 안 함")
    if u.GetForegroundWindow() != main:
        sys.exit("포커스 바뀜 — 입력 안 함")
    # 남은 검색어 지우기 — 키보드(Ctrl+A·Delete)는 안 먹어서 WM_SETTEXT (2026-11-06 「씨에버경기서부」로 이어 붙은 오류)
    u.SendMessageW(se, 0x000C, 0, ctypes.c_wchar_p(""))
    time.sleep(0.3)
    if get_text(se):
        sys.exit(f"검색칸에 남은 글자를 못 지움({get_text(se)}) — 입력 안 함")

    class KI(ctypes.Structure):
        _fields_ = [("vk", w.WORD), ("scan", w.WORD), ("flags", w.DWORD), ("time", w.DWORD), ("extra", ctypes.c_size_t)]

    class IN(ctypes.Structure):
        _fields_ = [("type", w.DWORD), ("k", KI), ("pad", ctypes.c_byte * 8)]
    for ch in q:
        if u.GetForegroundWindow() != main:
            sys.exit("포커스 바뀜 — 입력 중단")
        for f in (4, 6):
            i = IN(1, KI(0, ord(ch), f, 0, 0))
            u.SendInput(1, ctypes.byref(i), ctypes.sizeof(IN))
        time.sleep(0.03)
    time.sleep(1.2)
    shot = capture(main, SHOTS / f"{time.strftime('%y%m%d_%H%M%S')}_검색.png")
    if peek:  # 검색 결과만 보고 멈춤 — 첫 결과가 맞는 방인지 확인할 때 (2026-11-06)
        print(f"검색 결과 캡처: {shot} — 맞으면 --peek 없이 다시 실행")
        return
    if u.GetForegroundWindow() != main:
        sys.exit("포커스 바뀜 — Enter 안 누름")
    u.keybd_event(0x0D, 0, 0, 0)
    u.keybd_event(0x0D, 0, 2, 0)
    time.sleep(1.5)
    if was_min:
        u.ShowWindow(main, 6)
    hit = [t for _, t in rooms() if q.replace(" ", "") in t.replace(" ", "")]
    print(("열림: " + hit[0]) if hit else f"방 이름에 「{q}」가 없음 — 검색 캡처 확인: {shot}")


def cmd_save_photo(h, x, y):
    lc, cx, cy = list_point(h, x, y)
    before = files_now()
    old = {v for v, _, _ in windows()}
    lp = (cy << 16) | cx
    u.PostMessageW(lc, WM_MOUSEMOVE, 0, lp)
    time.sleep(0.2)
    u.PostMessageW(lc, WM_LDOWN, 1, lp)
    u.PostMessageW(lc, WM_LUP, 0, lp)
    time.sleep(0.05)
    u.PostMessageW(lc, WM_LDBL, 1, lp)
    u.PostMessageW(lc, WM_LUP, 0, lp)
    viewer = None
    for _ in range(20):
        time.sleep(0.3)
        viewer = next((v for v, t, c in windows() if v not in old and c == "EVA_Window_Dblclk" and t), None)
        if viewer:
            break
    if not viewer:
        sys.exit("사진 뷰어가 안 열림 — 좌표가 사진 위인지 캡처로 확인")
    time.sleep(1)
    L, T, R, B = rect(viewer)
    bx, by = (R - L) - 80, (B - T) - 32  # 오른쪽 아래 다운로드 버튼
    old2 = {v for v, _, _ in windows()}
    click(viewer, bx, by)
    note = answer_warning(h, old2, wait=1.5)
    if note:
        u.PostMessageW(viewer, WM_CLOSE, 0, 0)
        sys.exit("저장 안 됨 — " + note)
    dlg = None
    for _ in range(20):
        time.sleep(0.3)
        dlg = next((v for v, t, c in windows() if c == "#32770" and "저장" in t), None)
        if dlg:
            break
    if dlg:
        btn = next((c for c, k in children(dlg) if k == "Button" and u.GetDlgCtrlID(c) == 1), None)
        if btn:
            u.SendMessageW(btn, BM_CLICK, 0, 0)
    f = new_file(before)
    u.PostMessageW(viewer, WM_CLOSE, 0, 0)
    print(f"저장: {f}" if f else "저장 안 됨 — 저장 창이 떴는지·폴더 확인")


SENT_LOG = HERE / "state" / "sent_log.jsonl"
CR, LF, CRLF = chr(13), chr(10), chr(13) + chr(10)
PLACEHOLDER = "메시지 입력"  # 빈 입력칸이 돌려주는 안내 글자


def clip_get():
    k, us = ctypes.windll.kernel32, u
    k.GlobalLock.restype = ctypes.c_void_p
    us.GetClipboardData.restype = ctypes.c_void_p
    if not us.OpenClipboard(0):
        return None
    try:
        hd = us.GetClipboardData(13)  # CF_UNICODETEXT
        if not hd:
            return None
        ptr = k.GlobalLock(ctypes.c_void_p(hd))
        try:
            return ctypes.wstring_at(ptr)
        finally:
            k.GlobalUnlock(ctypes.c_void_p(hd))
    finally:
        us.CloseClipboard()


def clip_set(s):
    k = ctypes.windll.kernel32
    k.GlobalAlloc.restype = ctypes.c_void_p
    k.GlobalLock.restype = ctypes.c_void_p
    u.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    if not u.OpenClipboard(0):
        return False
    try:
        u.EmptyClipboard()
        if s is None:
            return True
        data = (s + "\0").encode("utf-16-le")
        hm = k.GlobalAlloc(0x0002, len(data))
        ctypes.memmove(k.GlobalLock(ctypes.c_void_p(hm)), data, len(data))
        k.GlobalUnlock(ctypes.c_void_p(hm))
        return bool(u.SetClipboardData(13, hm))
    finally:
        u.CloseClipboard()


def yellow_box(h):
    """화면에 실제로 보이는 「전송」 노란 영역 (화면 좌표) — 없으면 None. 방 창이 앞에 있을 때만 의미 있음"""
    from PIL import ImageGrab
    L, T, R, B = rect(h)
    im = ImageGrab.grab(bbox=(R - 260, B - 100, R, B), all_screens=True).convert("RGB")
    pts = [(x, y) for y in range(im.size[1]) for x in range(im.size[0])
           if (lambda c: c[0] > 230 and c[1] > 200 and c[2] < 80)(im.getpixel((x, y)))]
    if len(pts) < 200:
        return None
    xs, ys = [x for x, _ in pts], [y for _, y in pts]
    return R - 260 + min(xs), B - 100 + min(ys), R - 260 + max(xs), B - 100 + max(ys)


def cmd_send(h, msg):
    """방에 글 보내기 (2026-11-06 사용자 「카톡 발송은 류호정 계정으로 에이전트가 한다」)
    시험으로 확정한 방법: 카톡은 사람이 입력칸을 클릭하고 붙여넣기/타이핑해야 「전송」을 켠다(노란색).
    WM_SETTEXT·WM_CHAR·백그라운드 Enter·키보드 End/Enter만으로는 회색 그대로 → 방 창을 앞으로, 입력칸을 진짜 클릭, Ctrl+V.
    화면·마우스·클립보드를 2~3초 쓴다(마우스 위치·클립보드 글자는 되돌려 놓음). 매 단계 확인, 하나라도 다르면 지우고 멈춤"""
    import json
    to_main_monitor(h)
    edit = next((c for c, k in children(h) if k == "RICHEDIT50W"), None)
    if not edit:
        sys.exit("입력칸 없음 — 보내지 않음")
    empty = lambda: get_text(edit).strip() in ("", PLACEHOLDER)
    if not empty():
        sys.exit("입력칸에 쓰던 글자가 있음 — 사람이 작업 중일 수 있어 보내지 않음")

    def stop(why):
        u.SendMessageW(edit, 0x000C, 0, ctypes.c_wchar_p(""))
        clip_set(old_clip)
        sys.exit(why + " — 지우고 보내지 않음")

    old_clip = clip_get()
    if not clip_set(msg):
        sys.exit("클립보드를 못 씀 — 보내지 않음")
    u.keybd_event(0x12, 0, 0, 0)
    u.SetForegroundWindow(h)
    u.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.5)
    if u.GetForegroundWindow() != h:
        stop("방 창이 앞으로 안 옴")
    l, t_, r, b = rect(edit)
    pt = w.POINT()
    u.GetCursorPos(ctypes.byref(pt))
    u.SetCursorPos((l + r) // 2, (t_ + b) // 2)
    u.mouse_event(2, 0, 0, 0, 0)
    u.mouse_event(4, 0, 0, 0, 0)
    time.sleep(0.3)
    u.SetCursorPos(pt.x, pt.y)
    if u.GetForegroundWindow() != h:
        stop("클릭 뒤 앞 창이 바뀜")
    for vk, up in ((0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2)):  # Ctrl+V
        u.keybd_event(vk, 0, up, 0)
    time.sleep(0.6)
    clip_set(old_clip)
    if get_text(edit).replace(CRLF, LF).replace(CR, LF) != msg.replace(CRLF, LF):
        stop("입력칸 글자가 보낼 글과 다름")
    box = yellow_box(h)
    if not box or u.GetForegroundWindow() != h:
        stop("「전송」이 안 켜짐 또는 앞 창 바뀜")
    L, T, _, _ = rect(h)
    x0, y0, x1, y1 = box
    click(h, x0 + (x1 - x0) // 4 - L, (y0 + y1) // 2 - T)  # 노란 영역 왼쪽 1/4 = 「전송」(오른쪽 ∨ 메뉴 피함)
    time.sleep(1.5)
    sent = empty()
    shot = capture(h, SHOTS / f"{time.strftime('%y%m%d_%H%M%S')}_발송후.png")
    SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "room": text(h), "msg": msg, "sent": sent,
                            "shot": str(shot)}, ensure_ascii=False) + "\n")
    print(("보냄" if sent else "입력칸에 글자가 남음 — 안 보내졌을 수 있음") + f" · 확인 캡처: {shot}")


class ScreenTurn:
    """카톡 화면 순번 — 담당 여럿이 동시에 카톡을 쓰면 서로 방을 스크롤·앞으로 띄워 엉킴 → 한 번에 하나만 (2026-11-06)
    rooms 외 모든 명령이 차례를 기다린다(최대 5분). 프로세스가 죽으면 OS가 잠금을 풀어 줌"""
    def __init__(self, wait=300):
        self.wait = wait

    def __enter__(self):
        import msvcrt
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(LOCK, "a+")
        end = time.time() + self.wait
        while True:
            try:
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.time() > end:
                    sys.exit("다른 작업이 카톡을 쓰는 중(5분 넘게) — 나중에 다시")
                time.sleep(1)

    def __exit__(self, *a):
        import msvcrt
        try:
            self.f.seek(0)
            msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.f.close()


LOCK = HERE / "state" / "screen.lock"


def main():
    if len(sys.argv) > 1 and sys.argv[1] not in ("rooms", "-h", "--help"):
        with ScreenTurn():
            return _main()
    return _main()


def _main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("rooms")
    sp.add_parser("shot").add_argument("room")
    s = sp.add_parser("open")
    s.add_argument("room")
    s.add_argument("--peek", action="store_true", help="검색 결과만 캡처하고 Enter 안 누름")
    s = sp.add_parser("scroll")
    s.add_argument("room")
    s.add_argument("dir", choices=["up", "down", "bottom"])
    s.add_argument("n", type=int, nargs="?", default=5)
    for n in ("save-file", "save-photo"):
        s = sp.add_parser(n)
        s.add_argument("room")
        s.add_argument("x", type=int)
        s.add_argument("y", type=int)
    s = sp.add_parser("send")
    s.add_argument("room", help="방 이름 — 열린 방 중 하나에만 맞아야 함")
    s.add_argument("message")
    s.add_argument("--confirm", action="store_true", help="승인 받은 발송만. 없으면 미리보기")
    a = ap.parse_args()

    if a.cmd == "send":
        h = room(a.room)
        if not a.confirm:
            print(f"미리보기 — 방: {text(h)} / 글: {a.message} (보내려면 --confirm)")
            return
        return cmd_send(h, a.message)
    if a.cmd == "rooms":
        for h, t in rooms():
            print(f"{t}{'  (최소화)' if u.IsIconic(h) else ''}")
        return
    if a.cmd == "open":
        return cmd_open(a.room, a.peek)
    h = room(a.room)
    if a.cmd == "shot":
        if u.IsIconic(h):
            u.ShowWindow(h, 4)  # SW_SHOWNOACTIVATE
            time.sleep(0.5)
        print(capture(h, SHOTS / f"{time.strftime('%y%m%d_%H%M%S')}_{text(h)[:20].replace('/', '_').replace(' ', '')}.png"))
    elif a.cmd == "scroll":
        lc = list_ctrl(h)
        L, T, R, B = rect(lc)
        x, y = (L + R) // 2, (T + B) // 2
        n, d = (300, -120) if a.dir == "bottom" else (a.n, 120 if a.dir == "up" else -120)
        for _ in range(n):
            u.PostMessageW(lc, WM_WHEEL, (d & 0xffff) << 16, (y << 16) | (x & 0xffff))
            time.sleep(0.03)
        time.sleep(0.8)
        print("스크롤 완료 — shot 으로 다시 확인")
    elif a.cmd in ("save-file", "save-photo"):
        if to_main_monitor(h):
            sys.exit("방 창을 주 모니터로 옮김 — 좌표가 바뀌었으니 shot 을 다시 찍고 좌표를 다시 정해서 실행")
        if a.cmd == "save-photo":
            return cmd_save_photo(h, a.x, a.y)
        lc, cx, cy = list_point(h, a.x, a.y)
        before = files_now()
        old = {v for v, _, _ in windows()}
        lp = (cy << 16) | cx
        u.PostMessageW(lc, WM_MOUSEMOVE, 0, lp)
        time.sleep(0.2)
        u.PostMessageW(lc, WM_LDOWN, 1, lp)
        time.sleep(0.08)
        u.PostMessageW(lc, WM_LUP, 0, lp)
        note = answer_warning(h, old)
        f = new_file(before)
        print(f"저장: {f}" if f else f"저장 안 됨 — {note or '「저장」 글자 위 좌표인지, 이미 저장된 파일(「열기」로 표시)인지 확인'}")


if __name__ == "__main__":
    main()
