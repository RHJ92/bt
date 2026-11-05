# 제때 ebiz 일일 조회 → DAILY 시트 「재고현황」·주간 매출 탭 갱신
# 실행(비교만, 시트 안 씀): python -X utf8 run_daily.py
# 실행(시트 씀):           python -X utf8 run_daily.py --write
# 규칙 원본: ../README.md §1·§4 — 제목행(1행)은 그대로 두고 2행부터 전체 교체, 블록마다 합계행
# 종합현황은 주간 열(K~O)의 머리글(4행)·탭 참조만 고친다 (사용자 승인 2026-11-02). 나머지 칸은 절대 안 건드림
# 새 주: 오늘이 든 탭이 없으면 가장 오래된 주 탭 이름을 이번 주(월~토)로 바꾸고 맨 앞으로 옮긴 뒤 K~O를 맞춘다

import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
from pathlib import Path

import requests

from ebiz import Ebiz, retrying_session

SHEET_ID = "1x1KueQVbAyKYQJV_3pkcHZhJc5YJqjSbadiCIr3tRns"
CRED_DIR = Path(r"C:\Users\BLUETREND\.gdrive-mcp")
STATE = Path(__file__).resolve().parents[1] / "state"
LAST_COL = "AH"
LAST_COL_N = 34
http = retrying_session()  # 부팅 직후 네트워크가 끊기면 몇 번 다시 시도 (2026-11-02 10053 실패)

# 재고현황 블록: (계정 별칭, 고객사 OWNERID, 매입사 VENDORID). 순서 = 시트 블록 순서
STOCK_BLOCKS = [("옥된장", "3680", "JT01036"),   # 블루푸드랩
                ("옥된장", "3680", "JT01057"),   # 블루트렌드
                ("철산장", "4061", None)]        # 철산장 전체 — 계정 확인 후 확정
SALES_ACCOUNTS = ["옥된장", "철산장"]

STOCK_COLS = ["OWNERID", "OWNERNAME", "ITEMID", "ITEMNAME", "ALERT_STOCK_GUBUN", "EXPIRY_DATE", "SALE_UNIT",
              "STOCK_TYPE", "ITEM_USING", "NOW_STOCK", "ING_OUT_STOCK", "USELESS_STOCK", "POSSIBLE_STOCK", "OM_QTY",
              "OUT_QTY", "TOTAL_OM_QTY", "LACK_QTY", "MONTH_OUT_QTY", "WEEK_OUT_QTY", "DAY_OUT_QTY", "TURNOVER",
              "LEAD_TIME", "IN_QTY", "SAFE_STOCK", "SUPPLEMENT_QTY", "MIN_PO_QTY", "PREDICT_PO_QTY", "STATUS", "VENDORID"]
STOCK_SUM = {"NOW_STOCK", "ING_OUT_STOCK", "USELESS_STOCK", "POSSIBLE_STOCK", "OM_QTY", "OUT_QTY", "TOTAL_OM_QTY",
             "LACK_QTY", "IN_QTY", "SAFE_STOCK", "SUPPLEMENT_QTY", "PREDICT_PO_QTY"}
SALES_COLS = ["SHIPPING_DATE", "ORDER_DATE", "ORDER_TYPE", "ORDER_STATE", "BRANDNAME", "SHOPNAME", "CENTERID",
              "CENTERNAME", "ITEMID", "ITEMNAME", "ITEM_USING", "CATEGORY1_NAME", "SALE_UNIT", "TAX_GUBUN", "OM_QTY",
              "OUT_QTY", "NO_QUT_QTY", "UNIT_PRICE", "SUPPLY_PRICE", "VAT", "TOTAL_AMOUNT", "RETURN_DATE",
              "RETURN_REASON", "TEMP_GUBUN", "ORDER_NO", "LINE_NO", "OUT_BY", "OWNER_ITEMID", "OUT_SHOPID", "SHOPID",
              "BUSINESS_NO", "CREATE_BY", "UPDATE_BY"]
SALES_SUM = {"OM_QTY", "OUT_QTY", "NO_QUT_QTY", "SUPPLY_PRICE", "VAT", "TOTAL_AMOUNT"}
DATE_COLS = {"EXPIRY_DATE", "SHIPPING_DATE", "ORDER_DATE", "RETURN_DATE"}


# ---------- 시트 ----------
def g_token(rw):
    keys = json.loads((CRED_DIR / "gcp-oauth.keys.json").read_text(encoding="utf-8"))["installed"]
    cred = json.loads((CRED_DIR / ("credentials_rw.json" if rw else "credentials.json")).read_text(encoding="utf-8"))
    r = http.post("https://oauth2.googleapis.com/token", timeout=60, data={
        "client_id": keys["client_id"], "client_secret": keys["client_secret"],
        "refresh_token": cred["refresh_token"], "grant_type": "refresh_token"})
    r.raise_for_status()
    return r.json()["access_token"]


def sheet_url(path):
    return f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}{path}"


def get_values(tok, rng, render="UNFORMATTED_VALUE"):
    r = http.get(sheet_url(f"/values/{urllib.parse.quote(rng)}?valueRenderOption={render}"),
                 headers={"Authorization": "Bearer " + tok}, timeout=120)
    r.raise_for_status()
    return r.json().get("values", [])


def tab_titles(tok):
    r = http.get(sheet_url("?fields=sheets.properties.title"), headers={"Authorization": "Bearer " + tok}, timeout=60)
    r.raise_for_status()
    return [s["properties"]["title"] for s in r.json()["sheets"]]


def prepare_tab(tok, tab, n_rows):
    """쓰기 전: 2행 아래 병합 해제(옛 합계행 자리의 병합이 데이터를 삼킴), 행이 모자라면 추가. 1행 제목은 그대로"""
    h = {"Authorization": "Bearer " + tok}
    r = http.get(sheet_url("?fields=sheets(properties(title,sheetId,gridProperties),merges)"), headers=h, timeout=60)
    r.raise_for_status()
    sh = next(x for x in r.json()["sheets"] if x["properties"]["title"] == tab)
    sid, rows_now = sh["properties"]["sheetId"], sh["properties"]["gridProperties"]["rowCount"]
    reqs = []
    merges = [m for m in sh.get("merges", []) if m["startRowIndex"] >= 1]
    if merges:
        reqs.append({"unmergeCells": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": rows_now,
                                                "startColumnIndex": 0, "endColumnIndex": LAST_COL_N}}})
    if n_rows + 1 > rows_now:
        reqs.append({"appendDimension": {"sheetId": sid, "dimension": "ROWS", "length": n_rows + 1 - rows_now}})
    if reqs:
        http.post(sheet_url(":batchUpdate"), headers=h, json={"requests": reqs}, timeout=120).raise_for_status()
    print(f"{tab}: 병합 해제 {len(merges)}곳 · 행 추가 {max(0, n_rows + 1 - rows_now)}행")


def replace_body(tok, tab, rows):
    """2행~끝(A:AH) 값만 지우고 rows를 2행부터 씀. 서식·1행 제목은 유지"""
    h = {"Authorization": "Bearer " + tok}
    r = http.post(sheet_url(f"/values/{urllib.parse.quote(f'{tab}!A2:{LAST_COL}')}:clear"), headers=h, timeout=120)
    r.raise_for_status()
    r = http.put(sheet_url(f"/values/{urllib.parse.quote(f'{tab}!A2')}?valueInputOption=USER_ENTERED"),
                 headers=h, json={"values": rows}, timeout=300)
    r.raise_for_status()


def bad_rows(got, expected, col):
    """쓴 값과 다시 읽은 값의 제품코드 대조 — 행수가 맞아도 셀이 비면 종합현황 VLOOKUP이 조용히 깨짐"""
    out = []
    for i, want in enumerate(expected):
        row = got[i] if i < len(got) else []
        have = row[col] if col < len(row) else ""
        if str(have) != str(want[col]):
            out.append(i + 2)
    return out


# ---------- 변환 ----------
def cell(col, v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():  # 4.0 → 4 (붙여넣기 때와 같은 모양)
        return int(v)
    if col in DATE_COLS and isinstance(v, str):
        m = re.fullmatch(r"(\d{4})-?(\d{2})-?(\d{2}).*", v)
        if m:
            return "-".join(m.groups())
    return v


def block(data, cols, sums):
    """No 붙인 데이터행 + 합계행 (ebiz 화면 그리드를 복사한 모양)"""
    rows = [[i] + [cell(c, d.get(c)) for c in cols] for i, d in enumerate(data, 1)]
    total = ["", "합계"] + [""] * (len(cols) - 1)
    for j, c in enumerate(cols, 1):
        if c in sums:
            total[j] = round(sum(float(d.get(c) or 0) for d in data), 2)
    return rows + [total]


def week_tab(titles, today):
    """오늘이 들어 있는 MMDD~MMDD 탭"""
    for t in titles:
        m = re.fullmatch(r"(\d{2})(\d{2})~(\d{2})(\d{2})", t)
        if not m:
            continue
        for y in (today.year - 1, today.year):  # 연말 걸침(1229~0103)이면 시작이 작년일 수 있음
            a = dt.date(y, int(m[1]), int(m[2]))
            b = dt.date(y + (int(m[3]) < int(m[1])), int(m[3]), int(m[4]))
            if a <= today <= b:
                return t, a, b
    return None


def week_list(titles, today):
    """주간 탭 → 오래된 순 [(시작일, 탭 이름)]"""
    out = []
    for t in titles:
        m = re.fullmatch(r"(\d{2})(\d{2})~\d{4}", t)
        if m:
            a = dt.date(today.year, int(m[1]), int(m[2]))
            if a > today + dt.timedelta(days=14):  # 1월에 12월 탭
                a = a.replace(year=a.year - 1)
            elif (today - a).days > 180:  # 12월에 1월 탭
                a = a.replace(year=a.year + 1)
            out.append((a, t))
    return sorted(out)


def renew_tab(tok, old, new):
    """가장 오래된 주 탭 이름 변경 + 주간 탭 맨 앞 자리로 이동. 수식은 이름을 따라옴"""
    h = {"Authorization": "Bearer " + tok}
    r = http.get(sheet_url("?fields=sheets.properties(title,sheetId,index)"), headers=h, timeout=60)
    r.raise_for_status()
    props = [x["properties"] for x in r.json()["sheets"]]
    sid = next(p["sheetId"] for p in props if p["title"] == old)
    first = min(p["index"] for p in props if re.fullmatch(r"\d{4}~\d{4}", p["title"]))
    http.post(sheet_url(":batchUpdate"), headers=h, timeout=60, json={"requests": [{"updateSheetProperties": {
        "properties": {"sheetId": sid, "title": new, "index": first}, "fields": "title,index"}}]}).raise_for_status()


def align_summary(tok, wtok, today):
    """종합현황 K~O 머리글·SUMIFS 탭을 오래된 주 → 최신 주 순서로 맞춤. 고친 칸 수 반환, 예상과 다른 구조면 예외"""
    want = [t for _, t in week_list(tab_titles(tok), today)]
    if len(want) != 5:
        raise RuntimeError(f"주간 탭이 {len(want)}개 — 5개가 아니라 종합현황을 맞출 수 없음")
    head = (get_values(tok, "종합현황!K4:O4") or [[]])[0]
    if len(head) != 5 or not all(re.fullmatch(r"\d{4}~\d{4}", str(c)) for c in head):
        raise RuntimeError(f"종합현황 K4:O4 머리글이 예상과 다름: {head}")
    data, cells = [], 0
    pat = re.compile(r"=SUMIFS\('(\d{4}~\d{4})'!\$Q:\$Q,'\1'!\$J:\$J,G\d+\)")
    for i, row in enumerate(get_values(tok, "종합현황!K15:O", "FORMULA"), 15):
        hits = [pat.fullmatch(str(c)) for c in row]
        if not any(hits):
            continue
        if len(row) != 5 or not all(hits):
            raise RuntimeError(f"종합현황 {i}행 K~O 수식이 예상과 다름")
        new = [c.replace(m[1], w) for c, m, w in zip(row, hits, want)]
        if new != row:
            data.append({"range": f"종합현황!K{i}:O{i}", "values": [new]})
            cells += sum(a != b for a, b in zip(new, row))
    if head != want:
        data.append({"range": "종합현황!K4:O4", "values": [want]})
        cells += sum(a != b for a, b in zip(head, want))
    if data:
        (STATE / f"종합현황_정렬전_{today:%y%m%d}.json").write_text(json.dumps(
            {"머리글": head, "수식": get_values(tok, "종합현황!K15:O", "FORMULA")}, ensure_ascii=False), encoding="utf-8")
        http.post(sheet_url("/values:batchUpdate"), headers={"Authorization": "Bearer " + wtok}, timeout=120, json={
            "valueInputOption": "USER_ENTERED", "data": data}).raise_for_status()
    return cells


# ---------- 실행 ----------
def fetch(today, wk_tab, wk_from, wk_to):
    """계정별로 한 번씩 로그인해 재고 3블록·매출 2블록 조회"""
    stock_rows, sales_rows, info, sessions = [], [], [], {}

    def ses(alias):
        if alias not in sessions:
            sessions[alias] = Ebiz.from_alias(alias).login()
        return sessions[alias]

    try:
        yymmdd = (today + dt.timedelta(days=1)).strftime("%Y%m%d")  # 화면 기본값 = 내일
        for alias, owner, vendor in STOCK_BLOCKS:
            data = ses(alias).stock(yymmdd, owner, vendor)
            stock_rows += block(data, STOCK_COLS, STOCK_SUM)
            info.append(f"재고 {alias} {vendor or '전체'}: {len(data)}행")
        for alias in SALES_ACCOUNTS:
            data = ses(alias).sales(wk_from.strftime("%Y%m%d"), wk_to.strftime("%Y%m%d"))
            sales_rows += block(data, SALES_COLS, SALES_SUM)
            info.append(f"매출 {alias} {wk_tab}: {len(data)}행")
    finally:
        for e in sessions.values():
            e.logout()
    return stock_rows, sales_rows, info


def refresh_prev_week(tok, wtok, titles, wk_from):
    """새 주로 넘어가는 날 지난주 탭을 한 번 더 받아 덮어씀 — 토요일에 안 돌아서(2026-11-05 월~금 전환)
    금요일 갱신 뒤 잡힌 토요일 출고분이 빠지지 않게. 지난주 탭이 없거나 새 조회가 지금의 절반 미만이면 건드리지 않음"""
    p_from, p_to = wk_from - dt.timedelta(days=7), wk_from - dt.timedelta(days=2)
    tab = f"{p_from:%m%d}~{p_to:%m%d}"
    if tab not in titles:
        return f"지난주 탭 {tab} 없음 — 보충 안 함"
    rows, sessions = [], {}
    try:
        for alias in SALES_ACCOUNTS:
            sessions[alias] = Ebiz.from_alias(alias).login()
            rows += block(sessions[alias].sales(p_from.strftime("%Y%m%d"), p_to.strftime("%Y%m%d")), SALES_COLS, SALES_SUM)
    finally:
        for e in sessions.values():
            e.logout()
    cur = get_values(tok, f"'{tab}'!A2:{LAST_COL}")
    if len(cur) > 20 and len(rows) < len(cur) * 0.5:
        return f"지난주 탭 {tab} 보충 안 함 — 새 조회 {len(rows)}행이 지금 {len(cur)}행의 절반 미만"
    (STATE / f"{dt.datetime.now():%y%m%d_%H%M%S}_prevweek_backup.json").write_text(
        json.dumps({tab: cur}, ensure_ascii=False), encoding="utf-8")
    prepare_tab(wtok, tab, len(rows))
    replace_body(wtok, f"'{tab}'", rows)
    return f"지난주 {tab} 토요일분까지 다시 받음 {len(cur)}→{len(rows)}행"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="시트에 씀 (없으면 비교만)")
    ap.add_argument("--date", help="기준일 YYYY-MM-DD (기본 오늘)")
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.date) if a.date else dt.date.today()

    tok = g_token(rw=False)
    titles = tab_titles(tok)
    wk = week_tab(titles, today)
    renew_from = None
    if wk:
        wk_tab, wk_from, wk_to = wk
    else:
        weeks = week_list(titles, today)
        wk_from = today - dt.timedelta(days=today.weekday())
        wk_to = wk_from + dt.timedelta(days=5)
        wk_tab = f"{wk_from:%m%d}~{wk_to:%m%d}"
        if today.weekday() == 6 or len(weeks) != 5 or wk_tab in titles:
            print(f"STATUS: 중단 · {today:%m/%d}이 들어 있는 주간 탭이 없고 자동 리뉴얼 조건도 안 맞음 — 시트 안 건드림")
            sys.exit(2)
        renew_from = weeks[0][1]
        print(f"새 주 리뉴얼 예정: {renew_from} → {wk_tab}")
    stock_rows, sales_rows, info = fetch(today, wk_tab, wk_from, wk_to)

    print("\n".join(info))
    STATE.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%y%m%d_%H%M%S")

    # 비교: 지금 시트 행수와
    cur_stock = get_values(tok, f"재고현황!A2:{LAST_COL}")
    cur_sales = get_values(tok, f"'{renew_from or wk_tab}'!A2:{LAST_COL}")
    print(f"재고현황: 시트 {len(cur_stock)}행 → 새 {len(stock_rows)}행")
    print(f"{wk_tab}: 시트 {len(cur_sales)}행 → 새 {len(sales_rows)}행")
    out = STATE / f"{stamp}_preview.json"
    out.write_text(json.dumps({"재고현황": stock_rows, wk_tab: sales_rows}, ensure_ascii=False), encoding="utf-8")
    print("미리보기:", out)

    for old in sorted(STATE.glob("*_preview.json"))[:-30] + sorted(STATE.glob("*_backup.json"))[:-30]:
        old.unlink()  # 최근 30회분만 보관

    if not a.write:
        print("\n(비교만 — 시트 안 씀. 쓰려면 --write)")
        return
    # 조회가 비정상적으로 적으면(ebiz 장애·권한 변경 등) 덮어쓰지 않음. 주간 탭은 이번 주 배송분끼리만 비교
    # (리뉴얼한 탭엔 지난 주 데이터가 들어 있어 월요일엔 행수가 크게 줄어드는 게 정상)
    a0, b0 = [(d - dt.date(1899, 12, 30)).days for d in (wk_from, wk_to)]
    cur_week = [x for x in cur_sales if len(x) > 1 and isinstance(x[1], (int, float)) and a0 <= x[1] <= b0]
    for name, cur, new in (("재고현황", cur_stock, stock_rows), (wk_tab, cur_week, sales_rows)):
        if len(cur) > 20 and len(new) < len(cur) * 0.5:
            print(f"STATUS: 중단 · {name} 새 조회 {len(new)}행이 지금 시트 {len(cur)}행의 절반 미만 — 시트 안 건드림")
            sys.exit(3)
    # 쓰기 전 현재 값 백업 → 잘못 쓰면 되돌릴 근거
    (STATE / f"{stamp}_backup.json").write_text(
        json.dumps({"재고현황": cur_stock, wk_tab: cur_sales}, ensure_ascii=False), encoding="utf-8")
    wtok = g_token(rw=True)
    prev_note = ""
    if renew_from:
        prev_note = refresh_prev_week(tok, wtok, titles, wk_from)
        print(prev_note)
        renew_tab(wtok, renew_from, wk_tab)
    fixed = align_summary(tok, wtok, today)
    print(f"종합현황 주간 열 정렬: {fixed}칸 수정")
    prepare_tab(wtok, "재고현황", len(stock_rows))
    prepare_tab(wtok, wk_tab, len(sales_rows))
    replace_body(wtok, "재고현황", stock_rows)
    replace_body(wtok, f"'{wk_tab}'", sales_rows)

    # 다시 읽어 행수 + 제품코드 확인 (재고현황 D열, 주간 탭 J열)
    got_stock = get_values(tok, f"재고현황!A2:{LAST_COL}")
    got_sales = get_values(tok, f"'{wk_tab}'!A2:{LAST_COL}")
    n_stock, n_sales = len(got_stock), len(got_sales)
    bad = bad_rows(got_stock, stock_rows, 3), bad_rows(got_sales, sales_rows, 9)
    ok = n_stock == len(stock_rows) and n_sales == len(sales_rows) and not any(bad)
    note = (f" · 새 주 리뉴얼 {renew_from} → {wk_tab}" if renew_from else "") + (f" · {prev_note}" if prev_note else "") \
        + (f" · 종합현황 주간 열 {fixed}칸 정렬" if fixed else "")
    print(f"STATUS: {'완료' if ok else '확인 필요'} · 재고현황 {n_stock}행 · {wk_tab} {n_sales}행{note}"
          + ("" if ok else f" (기대 {len(stock_rows)}·{len(sales_rows)}, 제품코드 불일치 재고 {bad[0][:10]} 매출 {bad[1][:10]})"))
    if not ok:
        sys.exit(4)


if __name__ == "__main__":
    main()
