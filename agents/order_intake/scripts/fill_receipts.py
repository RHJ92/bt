# 매일 아침: 제때 전산 「구매 정산내역 조회(CS06100) 2번 탭」의 매입 확정분 → 발주진행현황 입고확인(P 입고일자 · Q 입고수량)
# 실행(미리보기): python -X utf8 fill_receipts.py                  (아직 안 한 날 ~ 어제)
#        (시트 씀): python -X utf8 fill_receipts.py --write
#        날짜 지정: python -X utf8 fill_receipts.py --date 2026-10-29
# 규칙 (2026-10-30, 10월 시트 실제 입력 패턴으로 확인 — 사용자 요청)
#  - 대상: 정산 매입사 = 블루트렌드 인 매입입고·매입반품만 (블루푸드랩·정남식품 등 다른 매입사 줄은 사람도 비워 둠)
#  - 같은 코드 + 입고확인 빈 줄 + 수량 부호 같음 + 입고요청일(E)이 입고일 ±7일 → 그 줄 하나면 P·Q 입력
#  - 후보가 없거나 둘 이상이면 입력하지 않고 「확인 필요」로 보고 (반품 줄이 시트에 없을 때도)
#  - 쓰는 칸은 P·Q 뿐. 종합현황·다른 열은 건드리지 않음. 전산은 조회 API만 (마감 확정 API 안 씀)

import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "jette_daily" / "scripts"))
import gsheet  # noqa: E402
from ebiz import Ebiz  # noqa: E402
from parse_orders import TAB_RE, norm_date, order_tabs, to_int  # noqa: E402

STATE = Path(__file__).resolve().parents[1] / "state" / "receipts.json"
LOGS = Path(__file__).resolve().parents[1] / "logs"
WINDOW = 7


def receipts(e, day):
    """그날 매입 확정분 (블루트렌드 정산) → ({(코드, 구분): {"qty", "name", "type"}}, 단가 정정 재매입 목록)
    단가 정정 재매입: 같은 날 같은 코드에 반품(−n, 옛 단가)과 입고(+n, 새 단가)가 짝으로 잡힌 것 — 실물 입고가 아니라
    제때 보관 재고를 새 단가로 다시 매입한 전표라 P·Q에 넣지 않는다 (2026-11-04 사용자 확인: 쪽파김치·계란 11/1 단가 변동)"""
    rows = e._grid("CS06100/CS06100_GetGrid_TAB2", {
        ":YYMMDD": f"{day:%Y%m}01", ":FROM_DATE": f"{day:%Y%m%d}", ":END_DATE": f"{day:%Y%m%d}",
        ":VENDORID": None, ":CONFIRM_GUBUN": None})
    every = [r for r in rows if r["IN_TYPE"] in ("매입입고", "매입반품") and r["FIX_IN_DATE"] == f"{day:%Y-%m-%d}"]
    rows = [r for r in every if r["PAY_VENDORNAME"] == "블루트렌드"]
    reprice = []
    for ret in [r for r in rows if r["IN_TYPE"] == "매입반품"]:
        buy = next((r for r in rows if r["IN_TYPE"] == "매입입고" and r["ITEMID"] == ret["ITEMID"]
                    and r["FIX_IN_QTY"] == -ret["FIX_IN_QTY"] and r["UNIT_PRICE"] != ret["UNIT_PRICE"]), None)
        if buy:
            rows = [r for r in rows if r is not ret and r is not buy]
            reprice.append({"code": ret["ITEMID"], "name": ret["ITEMNAME"], "qty": buy["FIX_IN_QTY"],
                            "old": ret["UNIT_PRICE"], "new": buy["UNIT_PRICE"]})
            continue
        # 코드 간 재고 이동: 반품(−n)과 같은 날 품명이 같은 다른 코드 입고(+n, 정산 매입사 무관) — 옥된장↔철산장은 정산 구조가
        # 달라 같은 로트도 코드별로 재고를 따로 운영해서, 새 코드로 옮길 때 이렇게 잡힌다 (2026-11-04 오징어채 CC313772→CC315042)
        core = re.sub(r"[^가-힣]|new|NEW", "", ret["ITEMNAME"].split("(")[0])
        move = next((r for r in every if r["IN_TYPE"] == "매입입고" and r["ITEMID"] != ret["ITEMID"]
                     and r["FIX_IN_QTY"] == -ret["FIX_IN_QTY"]
                     and re.sub(r"[^가-힣]|new|NEW", "", r["ITEMNAME"].split("(")[0]) == core), None)
        if move:
            rows = [r for r in rows if r is not ret and r is not move]
            reprice.append({"code": ret["ITEMID"], "name": ret["ITEMNAME"], "qty": move["FIX_IN_QTY"],
                            "to": move["ITEMID"], "old": ret["UNIT_PRICE"], "new": move["UNIT_PRICE"]})
    out = defaultdict(lambda: {"qty": 0, "name": "", "type": ""})
    for r in rows:
        k = (r["ITEMID"], r["IN_TYPE"])
        out[k]["qty"] += r["FIX_IN_QTY"] or 0
        out[k]["name"], out[k]["type"] = r["ITEMNAME"], r["IN_TYPE"]
    return out, reprice


def tab_for(tok, day):
    tabs = order_tabs(gsheet.tab_titles(tok))  # 연도 붙은 탭 이름도 읽음 (2026-11-04)
    prev = day.replace(day=1) - dt.timedelta(days=1)
    return [tabs[k] for k in ((day.year, day.month), (prev.year, prev.month)) if k in tabs]


def sheet_rows(tok, tab):
    vals = gsheet.get_values(tok, f"'{tab}'!A1:Q")
    out = []
    for i, r in enumerate(vals, 1):
        if i < 5:
            continue
        r = r + [""] * (17 - len(r))
        code = r[7].strip()
        if code:
            out.append({"tab": tab, "row": i, "date": norm_date(r[4]), "code": code, "vendor": r[6],
                        "L": to_int(r[11]), "P": norm_date(r[15]), "Q": to_int(r[16]), "raw_P": r[15].strip()})
    return out


def match(day, code, qty, rows):
    same = [r for r in rows if r["code"] == code]
    if any(r["P"] == day and r["Q"] == qty for r in same):
        return "이미", None
    cand = [r for r in same if not r["raw_P"] and r["date"] and abs((r["date"] - day).days) <= WINDOW
            and (r["L"] or 0) * qty > 0]
    # 새 달 탭이 생기면 지난달 탭 아래쪽에 같은 줄이 남아 있음(2026-11) → 입고일이 속한 달 탭에 후보가 있으면 그 탭만 본다
    own = [r for r in cand if TAB_RE.fullmatch(r["tab"]) and int(TAB_RE.fullmatch(r["tab"])[2]) == day.month]
    cand = own or cand
    exact = [r for r in cand if r["date"] == day]
    if len(exact) == 1:
        return "입력", exact[0]
    if len(cand) == 1:
        return "입력", cand[0]
    if not cand:
        return "확인", "시트에 맞는 빈 줄 없음" + (" (반품 줄을 추가해야 할 수 있음)" if qty < 0 else "")
    return "확인", "후보 여러 줄: " + ", ".join(f"{r['tab'][:3]} {r['row']}행({r['date']:%m/%d} {r['L']})" for r in cand)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--date")
    a = ap.parse_args()
    today = dt.date.today()
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    if a.date:
        days = [dt.date.fromisoformat(a.date)]
    else:
        last = dt.date.fromisoformat(state.get("last", f"{today - dt.timedelta(days=2)}"))
        days = [last + dt.timedelta(days=i) for i in range(1, (today - last).days)]  # 마지막 처리일 다음 ~ 어제
    if not days:
        print("STATUS: 완료 · 오늘 처리할 날짜 없음 (이미 처리)")
        return

    e = Ebiz.from_alias("옥된장").login()
    tok = gsheet.token()
    lines, data, n_in, n_done, need = [], [], 0, 0, []
    notes = []  # 📌 특이사항 — 매입마감 때 슬랙에 같이 남김 (2026-11-04 사용자 요청)
    try:
        for day in days:
            got, reprice = receipts(e, day)
            rows = [r for t in tab_for(tok, day) for r in sheet_rows(tok, t)]
            lines.append(f"*{day:%m/%d} 매입 확정 {len(got)}건* (정산 매입사 블루트렌드)")
            for x in reprice:
                what = (f"코드 이동 → {x['to']}" if x.get("to") else
                        f"단가 정정 재매입 ({x['old']:,.0f}→{x['new']:,.0f}, 반품·재매입 짝)")
                lines.append(f"• 💱 {x['code']} {x['name'][:18]} {x['qty']:g} — {what} · 입고 아님, P·Q 안 씀")
                notes.append(f"{day:%m/%d} {x['name'][:14]}: " + (
                    f"{x['code']}→{x['to']} 코드 간 재고 이동 {x['qty']:g} — 옥된장·철산장은 코드별 재고 별도 운영, 실물 입출고 아님"
                    if x.get("to") else
                    f"단가 변동 반품·재매입 {x['qty']:g} ({x['old']:,.0f}→{x['new']:,.0f}) — 신_단가변동사항 확인, 재고 수량 변동 없음"))
            for (code, kind), x in sorted(got.items()):
                qty = int(x["qty"]) if float(x["qty"]).is_integer() else x["qty"]
                res, r = match(day, code, qty, rows)
                tag = f"{code} {x['name'][:18]} {qty}"
                if res == "이미":
                    n_done += 1
                    lines.append(f"• ☑️ {tag} — 이미 입력돼 있음")
                elif res == "입력":
                    n_in += 1
                    r["raw_P"] = "x"  # 같은 실행에서 같은 줄을 두 번 쓰지 않게
                    data += [{"range": f"'{r['tab']}'!P{r['row']}", "values": [[f"{day:%Y-%m-%d}"]]},
                             {"range": f"'{r['tab']}'!Q{r['row']}", "values": [[qty]]}]
                    gap = "" if r["date"] == day else f" (입고요청일 {r['date']:%m/%d})"
                    lines.append(f"• ✅ {tag} → {r['tab'][:3]} {r['row']}행{gap}" + ("" if a.write else " (미리보기)"))
                    if r["L"] and r["L"] != qty:
                        notes.append(f"{day:%m/%d} {x['name'][:14]}: 입고 {qty} ≠ 발주 {r['L']} — 확정 수량으로 입력, 지결은 입고수량 기준")
                else:
                    need.append(tag)
                    lines.append(f"• ⚠️ {tag} — {r}")
                    if qty > 0 and "빈 줄 없음" in r:
                        notes.append(f"{day:%m/%d} {x['name'][:14]}: 발주 줄 없음 — BT 보관 재고를 제때가 매입한 건이면 정상, 그 달 BT 재고에서 차감")
    finally:
        e.logout()

    if a.write and data:
        wtok = gsheet.token(rw=True)
        requests.post(f"https://sheets.googleapis.com/v4/spreadsheets/{gsheet.DAILY_SHEET}/values:batchUpdate",
                      headers={"Authorization": "Bearer " + wtok},
                      json={"valueInputOption": "USER_ENTERED", "data": data}).raise_for_status()
    if a.write and not a.date:
        state["last"] = f"{days[-1]}"
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text(json.dumps(state), encoding="utf-8")

    if notes:
        lines += ["", "*📌 특이사항*"] + [f"• {n}" for n in notes]
    LOGS.mkdir(exist_ok=True)
    (LOGS / f"{dt.datetime.now():%y%m%d_%H%M}_입고확인{'' if a.write else '_미리보기'}.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    span = f"{days[0]:%m/%d}" + (f"~{days[-1]:%m/%d}" if len(days) > 1 else "")
    print(f"\nSTATUS: {'완료' if a.write else '미리보기'} · {span} 입고확인 입력 {n_in}건 · 이미 입력 {n_done}건"
          + (f" · 확인 필요 {len(need)}건" if need else ""))


if __name__ == "__main__":
    main()
