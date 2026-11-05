# 구매팀 업무 화면 — 큰 탭(재고 관리 등) 아래 작은 탭 — 구글시트 재고 마감장을 읽어 보여 주기만 함 (쓰기 없음)
# 실행: 재고화면.bat 더블클릭 → http://127.0.0.1:8765  (이 PC에서만 열림)
# 원본: 재고 마감장 구글시트. 「새로고침」을 누르면 다시 읽는다

import datetime as dt
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "jette_daily" / "scripts"))
sys.path.insert(0, str(HERE.parent / "inventory_sync" / "scripts"))
from run_daily import g_token  # noqa: E402
import preship_sync  # noqa: E402

SHEET = "1DfGgHvHuecTGySam_TiNusUtohKFwGB4AtYG_8K_ErQ"
EPOCH = dt.date(1899, 12, 30)
PORT = 8765
PRESHIP = HERE.parent / "inventory_sync" / "state" / "preship_sheet.json"
NO_ORDER_DAYS = 7  # 분출 후 이 일수까지 마켓봄 주문번호가 없으면 이상 감지
CACHE = {}


def values(tok, tab):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}/values/{requests.utils.quote(chr(39) + tab + chr(39))}"
    r = requests.get(url, headers={"Authorization": "Bearer " + tok}, timeout=60,
                     params={"valueRenderOption": "UNFORMATTED_VALUE"})
    r.raise_for_status()
    return r.json().get("values", [])


def day(v):
    return str(EPOCH + dt.timedelta(days=int(v))) if isinstance(v, (int, float)) and v > 30000 else str(v or "")


def num(v):
    return v if isinstance(v, (int, float)) else 0


def table(raw, head_row, c0=0, c1=None, first=None):
    """시트 범위 → {cols, rows}. 머리글 줄바꿈 제거, 첫 열이 빈 줄은 제외, 일자 열은 날짜로"""
    head = [re.sub(r"\s+", " ", str(h)).strip() for h in raw[head_row - 1][c0:c1]]
    n = len(head)
    rows = []
    for i, r in enumerate(raw[head_row:], head_row + 1):
        cells = (list(r[c0:c1]) + [""] * n)[:n]
        if str(cells[first or 0]).strip() == "":
            continue
        row = [day(c) if re.search("일자|매입일|^일$", head[j]) else c for j, c in enumerate(cells)]
        rows.append(row)
    return {"cols": head, "rows": rows}


def read_preship(tok):
    if not PRESHIP.exists():
        return {"cols": [], "rows": []}
    sid = json.loads(PRESHIP.read_text(encoding="utf-8"))["id"]
    r = requests.get(f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{requests.utils.quote('신청!A2:N1000')}",
                     headers={"Authorization": "Bearer " + tok}, params={"valueRenderOption": "UNFORMATTED_VALUE"}, timeout=60)
    r.raise_for_status()
    v = r.json().get("values", [])
    head, rows = v[0], []
    for x in v[1:]:
        x = (x + [""] * len(head))[:len(head)]
        if str(x[3]).strip() and str(x[4]).strip():
            rows.append([day(c) if head[i] in ("신청일", "희망 수령일", "분출일") else c for i, c in enumerate(x)])
    return {"cols": head, "rows": rows}


def detect(preship, stock):
    """대시보드 이상 감지 — 슬랙으로 보내지 않고 화면에만"""
    out, today = [], dt.date.today()
    c = {n: i for i, n in enumerate(preship["cols"])}
    for r in preship["rows"]:
        state, shop = r[c["상태"]], f"{r[c['매장']]} · {r[c['품목']]} × {r[c['수량']]}"
        if state == "분출완료" and not str(r[c["마켓봄 주문번호"]]).strip():
            done = str(r[c["분출일"]])[:10]
            days = (today - dt.date.fromisoformat(done)).days if done else None
            if days is None or days >= NO_ORDER_DAYS:
                out.append(["분출 후 주문 없음", f"{shop} — 분출 후 {days if days is not None else '?'}일", "영업팀에 마켓봄 주문 요청"])
        elif not state:
            want = str(r[c["희망 수령일"]])[:10]
            if want and want < str(today):
                out.append(["분출 지연", f"{shop} — 희망 수령일 {want} 지남", "분출 후 상태 입력"])
            else:
                out.append(["분출 대기", f"{shop} — 희망 {want or '미입력'}", "분출 후 상태 입력"])
    q = stock["cols"].index("현재고")
    out += [["재고 마이너스", f"{x[0]} {x[q]}", "원장 확인"] for x in stock["rows"] if isinstance(x[q], (int, float)) and x[q] < 0]
    return out


def load():
    tok = g_token(False)
    # 2026-11-03 통합 시트 탭 이름 변경: 마켓봄 탭은 MK_ (마켓봄_월마감 → MK_월마감)
    tab = {"마켓봄_월마감": "MK_월마감", "축·수산·기타 재고 입력": "축·수산·기타 재고 입력", "재무팀 재고자산 명세": "재무팀 재고자산 명세"}
    raw = {t: values(tok, tab.get(t, "MK_" + t)) for t in ("품목 마스터", "입출고 원장 입력", "로트 마스터", "재고 현황", "월말 대사", "마켓봄_월마감",
                                                          "축·수산·기타 재고 입력", "재무팀 재고자산 명세", "아카이브(식기류 구원장)")}
    ledger = table(raw["입출고 원장 입력"], 2, 0, 9, first=1)
    try:
        preship_sync.sync(g_token(True))
    except Exception as e:
        print("선분출 폼 연동 실패:", e)
    preship = read_preship(tok)
    alerts = detect(preship, table(raw["재고 현황"], 2, 0, 11))
    close = raw["월말 대사"]
    CACHE.update({
        "at": f"{dt.datetime.now():%Y-%m-%d %H:%M}",
        "cutoff": day(close[0][1]) if len(close[0]) > 1 else "",
        "tabs": {
            "재고 현황": table(raw["재고 현황"], 2, 0, 11),
            "재고자산(원가품목)": table(raw["재고 현황"], 2, 11, 17),
            "브랜드 합계": table(raw["재고 현황"], 2, 18, 23),
            "로트 마스터": table(raw["로트 마스터"], 2),
            "입출고 원장": ledger,
            "품목 마스터": table(raw["품목 마스터"], 2),
            "월말 대사(로트)": table(close, 2, 0, 10),
            "월말 대사(유니폼 실사)": table(close, 2, 11, 17),
            "마켓봄 월마감": table(raw["마켓봄_월마감"], 2, 0, 10),
            "월마감 요약": table(raw["마켓봄_월마감"], 2, 10, 19),
            "축·수산·기타": table(raw["축·수산·기타 재고 입력"], 3),
            "재무팀 명세": table(raw["재무팀 재고자산 명세"], 11, 0, 14),
            "아카이브": table(raw["아카이브(식기류 구원장)"], 2, 0, 8, first=4),
            "유니폼 선분출": preship,
            "이상 감지": {"cols": ["구분", "내용", "조치"], "rows": alerts},
        }})


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json; charset=utf-8", code=200):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            if self.path.startswith("/api/data"):
                if "refresh=1" in self.path or not CACHE:
                    load()
                self._send(json.dumps(CACHE, ensure_ascii=False))
            else:
                self._send((HERE / "index.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        except Exception as e:
            self._send(json.dumps({"error": str(e)}, ensure_ascii=False), code=500)


if __name__ == "__main__":
    print(f"재고 화면: http://127.0.0.1:{PORT}  (창을 닫으면 꺼집니다)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
