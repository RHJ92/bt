# 매일: 마켓봄 9517 출고완료 주문 중 원장에 없는 건 → 입출고 원장에 자동 입력
# 실행: python -X utf8 ledger_daily.py [--dry]   (2026-11-01 이후 배송요청일, 어제까지. --dry 는 쓰지 않고 보여만 줌)
# 규칙은 ledger_october.py 와 같다. 유니폼·모자는 선출고 확인 전 자동 입력 금지(업무노트) → 별도 표시
# 자동 입력은 10월 대사 마감 후 켬 (사용자 지시 2026-11-03). 확인 필요 건·유니폼은 넣지 않고 슬랙으로 묻는다

import datetime as dt
import re
import sys

import requests

import fetch_orders
import ledger_october as lo
import ledger_preview as lp
import orders_read
import verify_migration as vm

SHEET = "1DfGgHvHuecTGySam_TiNusUtohKFwGB4AtYG_8K_ErQ"
START = "2026-11-01"
TAB = "MK_입출고 원장 입력"


def main():
    dry = "--dry" in sys.argv
    today = dt.date.today()
    lo.FROM, lo.TO = lp.serial(START), lp.serial(str(today - dt.timedelta(days=1)))
    path = fetch_orders.fetch(START, str(today + dt.timedelta(days=7)))["9517"]
    tok = lp.g_token(True)
    by_code, by_name = lp.masters(tok, SHEET)
    ledger = vm.values(tok, SHEET, TAB)
    entered = set()
    for r in ledger[2:]:
        r = r + [""] * (9 - len(r))
        m = re.search(r"[A-Za-z]{4}[a-z]{3}\d+", str(r[8]))
        if m:
            entered.add((m[0], r[4]))
    # 명화주방 재고가 있는 품목은 삼보 잔량을 넘겨 소진 후 명화 출고로 잡게 한다
    sambo_left = lo.titanium_left(tok, SHEET)
    rows, ask, skipped = lo.build(orders_read.read(path), by_code, by_name, entered, sambo_left)
    rows = [r for r in rows if lo.FROM <= r[0] <= lo.TO]  # 조정 파일의 10월 선출고 행 제외
    uniform = [r for r in rows if re.search("유니폼|모자", str(r[4]))]
    auto = [r for r in rows if r not in uniform]

    last = max(i for i, r in enumerate(ledger, 1) if r and str(r[0]).strip())
    if auto and not dry:
        end = last + len(auto)
        requests.post(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}/values:batchUpdate",
                      headers={"Authorization": "Bearer " + tok}, timeout=60, json={"valueInputOption": "RAW", "data": [
                          {"range": f"'{TAB}'!A{last + 1}:E{end}", "values": [r[:5] for r in auto]},
                          {"range": f"'{TAB}'!G{last + 1}:I{end}", "values": [[r[5], r[6], f"{r[7]} · 자동 입력 {today:%m/%d}"] for r in auto]}]}
                      ).raise_for_status()
    head = "미리보기 — 쓰지 않음" if dry else (f"원장 {last + 1}~{last + len(auto)}행 입력" if auto else "입력할 행 없음")
    print(f"*{today:%m/%d} 원장 자동 입력 (11월분)* — {head} · {len(auto)}행"
          + (f" · 유니폼·모자 {len(uniform)}행은 선출고 확인 후 입력" if uniform else ""))
    for r in auto[:25]:
        print(f"• {lp.EPOCH + dt.timedelta(days=r[0])} {str(r[2])[:14]} · {r[3]} · {r[4]} {r[6]:g}")
    for r in uniform:
        print(f"• 🎽 미입력 {lp.EPOCH + dt.timedelta(days=r[0])} {str(r[2])[:14]} · {r[3]} · {r[4]} {r[6]:g} — 선분출 포함 여부 알려 주세요")
    for a in ask:
        print(f"• ⚠️ 미입력 {a}")
    need = len(ask) + len(uniform)
    print(f"STATUS: 완료 · 원장 입력 {0 if dry else len(auto)}행" + (f" · 확인 필요 {need}건" if need else ""))


if __name__ == "__main__":
    main()
