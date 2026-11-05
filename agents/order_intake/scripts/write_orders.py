# 3단계: 새 제때 발주 메일 → 발주진행현황 맨 아래에 E·H·L 자동 입력. 수정·삭제는 목록만
# 실행(미리보기, 시트 안 씀): python -X utf8 write_orders.py
# 실행(시트 씀):             python -X utf8 write_orders.py --write
# 처음 한 번:                 python -X utf8 write_orders.py --mark-all   (지금까지 메일을 처리완료로 표시만)
# 처리한 메일은 ../state/processed.json 에 UID로 기록 — 웹메일 쪽 읽음·폴더는 건드리지 않음
# 쓰기 허용 범위: 최신 「N월_발주진행현황」 탭 E·H·L만 (README §3, 사용자 승인 2026-10-28)

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import requests

import parse_orders as po
from parse_orders import gsheet

STATE = Path(__file__).resolve().parents[1] / "state"
PROCESSED = STATE / "processed.json"
LOOKBACK_DAYS = 45  # 정정 회신의 원 발주를 찾을 만큼 넉넉히 읽고, 처리 여부는 UID로 거름


def load_processed():
    return set(json.loads(PROCESSED.read_text(encoding="utf-8"))) if PROCESSED.exists() else set()


def save_processed(uids):
    STATE.mkdir(exist_ok=True)
    PROCESSED.write_text(json.dumps(sorted(uids, key=int)), encoding="utf-8")


def last_used_row(tok, tab, sheet):
    """E·H·L 중 하나라도 값이 있는 마지막 행, 수식이 미리 깔린 마지막 행(A열)"""
    vals = gsheet.get_values(tok, f"'{tab}'!E1:L", sheet=sheet)
    def used(r):
        r = r + [""] * 8
        return any(str(r[j]).strip() for j in (0, 3, 7))  # E·H·L
    last = max((i for i, r in enumerate(vals, 1) if used(r)), default=4)
    a = gsheet.get_values(tok, f"'{tab}'!A1:A", "FORMULA", sheet=sheet)
    formula_last = max((i for i, r in enumerate(a, 1) if r and str(r[0]).startswith("=")), default=0)
    return last, formula_last


def plan(mails, processed, got):
    """새 메일만 → (시트에 쓸 행, 보고만 할 항목)"""
    acts = [a for a in po.actions(mails) if a["uid"] not in processed]
    write, report = [], []
    seen = set()
    for a in acts:
        k = (a["date"], a["code"])
        if a["act"] == "신규":
            have = got.get(k, [])
            if any(q == a["qty"] for _, q in have) or k in seen:
                report.append({**a, "result": "이미 있음 — 건너뜀"})
            elif have:
                report.append({**a, "result": "같은 날짜·코드 행이 수량 다르게 있음("
                               + ", ".join(f"{i}행 {q}" for i, q in have) + ") — 확인 필요"})
            else:
                write.append(a)
                seen.add(k)
        elif a["act"] == "제외":
            report.append({**a, "result": "당면 — 입력 안 함"})
        else:  # 수정·삭제·확인필요 → 2단계(슬랙 승인) 전까지 목록만 (README §6 기본값)
            have = got.get(k, [])
            where = ", ".join(f"{i}행 {q}" for i, q in have) or "시트에 없음"
            report.append({**a, "result": f"{a['act']} 필요 — 시트 {where} (자동 수정 안 함)"})
    return acts, write, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--mark-all", action="store_true", help="지금까지 메일을 처리완료로만 표시")
    ap.add_argument("--sheet", default=gsheet.DAILY_SHEET, help="시험용 복사본 시트 ID")
    a = ap.parse_args()

    mails = po.fetch(dt.date.today() - dt.timedelta(days=LOOKBACK_DAYS))
    processed = load_processed()
    if a.mark_all:
        save_processed(processed | {m["uid"] for m in mails})
        print(f"STATUS: 처리완료 표시 {len(mails)}통 — 다음 실행부터 새 메일만 다룸")
        return

    tok = gsheet.token()
    tab, got = po.sheet_rows(tok, sheet=a.sheet)
    acts, write, report = plan(mails, processed, got)
    new_uids = {x["uid"] for x in acts}

    lines = [f"**제때 발주 자동입력** ({dt.datetime.now():%Y-%m-%d %H:%M}, 시트 `{tab}`)", "",
             f"새 메일 {len(new_uids)}통 · 입력 {len(write)}행 · 보고 {len(report)}건", ""]
    rows_written = ""
    if write:
        last, formula_last = last_used_row(tok, tab, a.sheet)
        start = last + 1
        end = start + len(write) - 1
        if end > formula_last:
            print(f"STATUS: 중단 · 수식이 깔린 행({formula_last}행)이 모자람 — {end}행까지 필요. 시트 안 건드림")
            sys.exit(3)
        lines += ["**입력**", "", "| 행 | 입고요청일 | 코드 | 제품명 | 수량 | 메일 | 비고 |", "|---|---|---|---|---|---|---|"]
        lines += [f"| {start + i} | {w['date']} | {w['code']} | {w['name'][:30]} | {w['qty']} | {w['mail']} | {w['note']} |"
                  for i, w in enumerate(write)]
        if a.write:
            wtok = gsheet.token(rw=True)
            data = []
            for i, w in enumerate(write):
                r = start + i
                data += [{"range": f"'{tab}'!E{r}", "values": [[w["date"].isoformat()]]},
                         {"range": f"'{tab}'!H{r}", "values": [[w["code"]]]},
                         {"range": f"'{tab}'!L{r}", "values": [[w["qty"]]]}]
            requests.post(f"https://sheets.googleapis.com/v4/spreadsheets/{a.sheet}/values:batchUpdate",
                          headers={"Authorization": "Bearer " + wtok},
                          json={"valueInputOption": "USER_ENTERED", "data": data}).raise_for_status()
            # 다시 읽어 제품명(I열)이 풀렸는지 확인
            check = gsheet.get_values(tok, f"'{tab}'!E{start}:L{end}", sheet=a.sheet)
            bad = [start + i for i, r in enumerate(check)
                   if len(r) < 5 or not r[4].strip() or r[4].startswith("#") or r[3] != write[i]["code"]]
            if bad:
                lines += ["", f"⚠️ 제품명이 안 풀린 행: {bad} — 신_품목리스트에 코드가 없는지 확인"]
            rows_written = f"{start}~{end}행"
    if report:
        lines += ["", "**보고 (시트 안 바꿈)**", "", "| 처리 | 입고요청일 | 코드 | 제품명 | 수량 | 메일 | 결과 |",
                  "|---|---|---|---|---|---|---|"]
        for x in report:
            q = f"{x['prev']}→{x['qty']}" if x.get("prev") is not None else x["qty"]
            lines.append(f"| {x['act']} | {x['date'] or ''} | {x['code']} | {x['name'][:30]} | {q} | {x['mail']} | {x['result']} |")

    po.LOGS.mkdir(exist_ok=True)
    out = po.LOGS / f"{dt.datetime.now():%y%m%d_%H%M}_자동입력{'' if a.write else '_미리보기'}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if a.write:
        save_processed(processed | new_uids)
        try:  # 처리 끝난 발주 메일은 웹메일에서 「읽음」으로 (다른 사람이 누락으로 오해하지 않게)
            po.mark_seen(new_uids)
        except Exception as e:
            print(f"(읽음 표시 실패 — 입력은 정상: {e})")
    need = sum(1 for x in report if "확인 필요" in x["result"] or "필요 —" in x["result"])
    print(f"\nSTATUS: {'완료' if a.write else '미리보기'} · 새 메일 {len(new_uids)}통 · 입력 {len(write)}행"
          + (f"({rows_written})" if rows_written else "") + (f" · 확인 필요 {need}건" if need else ""))
    print("결과:", out)


if __name__ == "__main__":
    main()
