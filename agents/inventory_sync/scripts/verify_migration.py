# 재고 마감장 구글시트 변환본 대조 — 엑셀(저장된 계산값) ↔ 구글시트(재계산값) 전 칸 비교 + 오류 셀 목록 (읽기 전용)
# 실행: python -X utf8 verify_migration.py {구글시트 ID}

import datetime as dt
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "jette_daily" / "scripts"))
from run_daily import g_token  # noqa: E402

XLSX = Path(__file__).resolve().parents[3] / "inventory_management" / "stock" / "통합_재고관리(로트기반)_261102.xlsx"
ERR = re.compile(r"^#(NAME\?|REF!|N/A|VALUE!|DIV/0!|NUM!|ERROR!|NULL!)")


def col(n):
    s = ""
    while n:
        n, m = divmod(n - 1, 26)
        s = chr(65 + m) + s
    return s


def values(tok, sid, sheet):
    u = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{urllib.parse.quote(chr(39) + sheet + chr(39))}?valueRenderOption=UNFORMATTED_VALUE&dateTimeRenderOption=SERIAL_NUMBER"
    r = requests.get(u, headers={"Authorization": "Bearer " + tok}, timeout=120)
    r.raise_for_status()
    return r.json().get("values", [])


def norm(v):
    """엑셀 값 → 구글 UNFORMATTED 비교용"""
    if isinstance(v, dt.datetime):
        return (v - dt.datetime(1899, 12, 30)).total_seconds() / 86400
    if isinstance(v, dt.date):
        return (v - dt.date(1899, 12, 30)).days
    if isinstance(v, bool):
        return v
    return v


def same(a, b):
    a, b = norm(a), b
    if a in (None, "") and b in (None, ""):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 0.005
    return str(a).strip() == str(b).strip()


def main():
    sid = sys.argv[1]
    tok = g_token(True)
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    total_diff, errors, per = [], defaultdict(list), {}
    for ws in wb.worksheets:
        got = values(tok, sid, ws.title)
        n = d = 0
        for r, row in enumerate(ws.iter_rows(values_only=True), 1):
            g = got[r - 1] if r - 1 < len(got) else []
            for c, v in enumerate(row, 1):
                b = g[c - 1] if c - 1 < len(g) else ""
                if isinstance(b, str) and ERR.match(b):
                    errors[ws.title].append((f"{col(c)}{r}", b, v))
                if v in (None, "") and b in (None, ""):
                    continue
                n += 1
                if not same(v, b):
                    d += 1
                    total_diff.append((ws.title, f"{col(c)}{r}", v, b))
        per[ws.title] = (n, d)
        print(f"{ws.title}: 비교 {n}칸 · 차이 {d}칸 · 오류 {len(errors[ws.title])}칸")
    print("\n차이 시트별 첫 8건")
    seen = Counter()
    for s, a, v, b in total_diff:
        seen[s] += 1
        if seen[s] <= 8:
            print(f"  {s}!{a}: 엑셀 {str(v)[:40]!r} / 구글 {str(b)[:40]!r}")
    print("\n오류 셀")
    for s, items in errors.items():
        c = Counter(e for _, e, _ in items)
        if items:
            print(f"  {s}: {dict(c)} · {[a for a, _, _ in items[:40]]}")
    head = values(tok, sid, "재무팀 재고자산 명세")[:11]
    print("\n명세 상단")
    for i, row in enumerate(head, 1):
        print(i, [str(x)[:22] for x in row[:14]])


if __name__ == "__main__":
    main()
