# 마켓봄 9517 출고완료 주문 → 입출고 원장 출고행 차감안 (미리보기 — 시트에 쓰지 않음)
# 실행: python -X utf8 ledger_preview.py {주문 엑셀} {구글시트 ID}
# 규칙: 출고완료만, 일자 = 배송요청일, 디자인물·식자재·배송비 제외, 반품접수는 차감 안 하고 확인 필요 (README 「차감 규칙」)

import datetime as dt
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import classify
import orders_read
import verify_migration as vm
from verify_migration import g_token

EPOCH = dt.date(1899, 12, 30)


def serial(s):
    return (dt.date.fromisoformat(str(s)[:10]) - EPOCH).days


def masters(tok, sid):
    """상품코드(ERP)·마켓봄 품목명 → 품목 마스터 행, 품목코드 → 창고 (원장에서 가장 많이 쓴 창고)"""
    rows = vm.values(tok, sid, "MK_품목 마스터")
    head = [str(c).strip() for c in rows[1]]
    by_code, by_name = {}, {}
    for r in rows[2:]:
        d = dict(zip(head, r + [""] * (len(head) - len(r))))
        if d.get("품목코드"):
            if str(d.get("ERP코드")).strip():
                by_code[str(d["ERP코드"]).strip()] = d
            by_name[re.sub(r"\s+", "", str(d.get("마켓봄 품목명")))] = d
    return by_code, by_name


def plan(orders, by_code, by_name):
    out, ask, skip = [], [], Counter()
    for r in orders:
        name = str(r["상품명"])
        v, note = classify.vendor_of(r)
        if r["주문상태"] == "반품접수":
            ask.append((r, "반품접수 — 상세화면 확인"))
            continue
        if r["주문상태"] != "출고완료":
            skip[r["주문상태"]] += 1
            continue
        if v is None:
            skip[note] += 1
            continue
        code = str(r["상품코드"]).strip()
        code = code[:-2] if code.endswith(".0") else code
        m = by_code.get(code) or by_name.get(re.sub(r"\s+", "", name))
        if not m:
            skip["품목 마스터에 없음(재고 관리 품목 아님)"] += 1
            ask.append((r, f"품목 마스터에 없음 · 출고처 {v}"))
            continue
        out.append({"일자": serial(r["배송요청일"]), "지점": r["거래처"], "품목코드": m["품목코드"],
                    "수량": -classify.ship_qty(r, "삼보물류"), "주문번호": r["주문번호"], "상품명": name})
    return out, ask, skip


def main():
    path, sid = sys.argv[1], sys.argv[2]
    tok = g_token(True)
    orders = orders_read.read(path)
    by_code, by_name = masters(tok, sid)
    out, ask, skip = plan(orders, by_code, by_name)
    ledger = vm.values(tok, sid, "MK_입출고 원장 입력")
    human = []
    for i, r in enumerate(ledger[2:], 3):
        r = r + [""] * (9 - len(r))
        if r[1] == "출고" and "마켓봄" in str(r[8]):
            human.append({"행": i, "일자": r[0], "지점": r[2], "품목코드": r[4], "수량": r[7], "메모": r[8]})
    print(f"차감안 {len(out)}행 · 원장 마켓봄 출고 {len(human)}행 · 제외 {dict(skip)} · 확인 필요 {len(ask)}")
    key = lambda x: (x["일자"], x["품목코드"], float(x["수량"]))
    a, b = Counter(map(key, out)), Counter(map(key, human))
    lo, hi = min(k[0] for k in b), max(k[0] for k in b)
    inrange = Counter({k: n for k, n in a.items() if lo <= k[0] <= hi})
    print(f"원장 기간 {EPOCH + dt.timedelta(days=lo)} ~ {EPOCH + dt.timedelta(days=hi)} · 이 기간 차감안 {sum(inrange.values())}행")
    print("일치", sum((inrange & b).values()))
    only_plan, only_human = inrange - b, b - inrange
    print(f"차감안에만 {sum(only_plan.values())}행")
    for k, n in sorted(only_plan.items())[:25]:
        print("  ", EPOCH + dt.timedelta(days=k[0]), *k[1:], f"×{n}" if n > 1 else "")
    print(f"원장에만 {sum(only_human.values())}행")
    for k, n in sorted(only_human.items())[:25]:
        print("  ", EPOCH + dt.timedelta(days=k[0]), *k[1:], f"×{n}" if n > 1 else "")
    print("확인 필요 예시")
    for r, why in ask[:15]:
        print("  ", r["배송요청일"], str(r["상품명"])[:26], r["수량"], r["주문상태"], why)
    print("기간 뒤 차감안", sum(n for k, n in a.items() if k[0] > hi))


if __name__ == "__main__":
    main()
