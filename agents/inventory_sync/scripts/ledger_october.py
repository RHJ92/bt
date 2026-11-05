# 2026-10월 미입력분 차감안 — 확정 규칙 적용, 쓰기 없음. 결과: ../output/10월_원장_차감안.xlsx + 화면 요약
# 실행: python -X utf8 ledger_october.py {주문 엑셀} {구글시트 ID}

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

import classify
import ledger_preview as lp
import orders_read
import verify_migration as vm

BASE = Path(__file__).resolve().parents[1]
FROM, TO = lp.serial("2026-10-01"), lp.serial("2026-10-31")
ALIAS = {"국그릇": "국그릇 (304)"}  # 마켓봄 옛 상품(ERP 20)도 실물은 304 — 2026-11-03 통합 결정
WAREHOUSE = {"삼보물류": "삼보물류", "경인양행": "경인양행", "블루트렌드(본사)": "본사창고", "명화주방": "명화주방"}


def titanium_left(tok, sid):
    """명화주방 재고가 있는 품목 → 삼보 잔량 (원장 기준). 이 품목만 삼보 소진 후 명화로 나눈다"""
    stock = vm.values(tok, sid, "MK_재고 현황")
    col = {c: i for i, c in enumerate(stock[1])}
    return {r[0]: float(r[col["삼보물류"]] or 0) for r in stock[2:]
            if len(r) > col["명화주방"] and r[0] and float(r[col["명화주방"]] or 0) > 0}


def item_code(r, by_code, by_name):
    m = by_code.get(str(r["상품코드"]).strip().removesuffix(".0")) or by_name.get(re.sub(r"\s+", "", str(r["상품명"])))
    return ALIAS.get(m["품목코드"], m["품목코드"]) if m else None


def build(orders, by_code, by_name, entered, sambo_left=None):
    """sambo_left: 티타늄 품목코드 → 삼보 잔량. 잔량을 넘는 주문은 삼보 잔량 + 나머지 명화주방으로 나눈다"""
    sambo_left = dict(sambo_left or {})
    adj = json.loads((BASE / "선출고_조정.json").read_text(encoding="utf-8"))
    rows, ask, skipped = [], [], Counter()
    done = set()
    for r in sorted(orders, key=lambda r: str(r["배송요청일"])):
        oid, day = r["주문번호"], lp.serial(r["배송요청일"])
        if r["주문상태"] == "반품접수" and FROM <= day <= TO:
            ask.append(f"{r['거래처']} {r['상품명']} × {r['수량']:g} — 반품접수, 상세화면 확인")
        if r["주문상태"] != "출고완료" or not FROM <= day <= TO:
            continue
        # 조정은 유니폼·모자 줄에만 — 같은 주문의 티타늄 등은 아래 일반 규칙으로
        if oid in adj["주문"] and re.search("유니폼|모자", str(r["상품명"])):
            if oid not in done:
                done.add(oid)
                a = adj["주문"][oid]
                memo = f"마켓봄 {oid} · {a['비고']}"
                for code, q in a.get("경인양행", {}).items():
                    rows.append([day, "출고", r["거래처"], "경인양행", code, "", -q, memo])
                sp = a.get("본사창고")
                if sp:
                    for code, q in sp["품목"].items():
                        rows.append([lp.serial(sp["일자"]), "출고", r["거래처"], "본사창고", code, "", -q,
                                     f"유니폼 선출고 (교육 목적) · 본사창고 실물 출고 · 마켓봄 {oid}"])
            continue
        v = classify.vendor_of(r)[0]
        if v is None:
            skipped["구매팀 대상 아님"] += 1
            continue
        code = str(r["상품코드"]).strip().removesuffix(".0")
        m = by_code.get(code) or by_name.get(re.sub(r"\s+", "", str(r["상품명"])))
        name = str(r["상품명"])
        if not m and "모자 3ea" in name:
            m, qty = {"품목코드": "옥된장 모자"}, r["수량"] * 3
        elif not m:
            skipped[f"재고 품목 아님 ({v})"] += 1
            continue
        else:
            qty = classify.ship_qty(r, "삼보물류")
            m = {**m, "품목코드": ALIAS.get(m["품목코드"], m["품목코드"])}
        if (oid, m["품목코드"]) in entered:
            skipped["원장에 이미 있음"] += 1
            continue
        wh = WAREHOUSE.get(v)
        if not wh:
            ask.append(f"{r['거래처']} {name} — 창고 미정 ({v})")
            continue
        left = sambo_left.get(m["품목코드"])
        parts = [(wh, qty)]
        if wh == "삼보물류" and left is not None:
            parts = classify.split_titanium(qty, left)
            sambo_left[m["품목코드"]] = max(0, left - qty)
        for w, q in parts:
            memo = f"마켓봄 {oid}" + (f" · 삼보·명화 나눠 출고 (주문 {qty:g})" if len(parts) > 1 else "")
            rows.append([day, "출고", r["거래처"], w, m["품목코드"], "", -q, memo])
    for x in adj["주문없는_선출고"]:
        for code, q in x["품목"].items():
            rows.append([lp.serial(x["일자"]), "출고", x["매장"], x["창고"], code, "", -q, x["메모"]])
    return sorted(rows, key=lambda r: r[0]), ask, skipped


def main():
    path, sid = sys.argv[1], sys.argv[2]
    tok = lp.g_token(True)
    by_code, by_name = lp.masters(tok, sid)
    ledger = vm.values(tok, sid, "MK_입출고 원장 입력")
    entered, stock = set(), defaultdict(float)
    for r in ledger[2:]:
        r = r + [""] * (9 - len(r))
        if r[1]:
            stock[(r[4], r[3])] += float(r[7] or 0)
        m = re.search(r"[A-Za-z]{4}[a-z]{3}\d+", str(r[8]))
        if m:
            entered.add((m[0], r[4]))
    rows, ask, skipped = build(orders_read.read(path), by_code, by_name, entered)
    after = dict(stock)
    for r in rows:
        k = (r[4], r[3])
        after[k] = after.get(k, 0) + r[6]
    neg = {k: v for k, v in after.items() if v < 0}
    print(f"차감안 {len(rows)}행 · 제외 {dict(skipped)} · 확인 필요 {len(ask)}건")
    print("창고별", Counter(r[3] for r in rows), "수량", {w: sum(r[6] for r in rows if r[3] == w) for w in {r[3] for r in rows}})
    print("품목별 합계")
    tot = defaultdict(float)
    for r in rows:
        tot[(r[3], r[4])] += r[6]
    for k, v in sorted(tot.items()):
        print("  ", *k, f"{v:g}", "→ 잔량", f"{after.get(k, 0):g}", "(원장 재고 없음)" if k not in stock else "")
    print("마이너스 재고", neg)
    for a in ask:
        print("확인:", a)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "10월 차감안"
    ws.append(["일자", "구분", "지점/거래처", "창고", "품목코드", "로트번호", "수량(±)", "메모"])
    for r in rows:
        ws.append([str(lp.EPOCH + lp.dt.timedelta(days=r[0])), *r[1:]])
    for row in ws.iter_rows():
        for c in row:
            c.font = Font(name="맑은 고딕", size=12 if c.row == 1 else 9, bold=c.row == 1)
    (BASE / "output").mkdir(exist_ok=True)
    wb.save(BASE / "output" / "10월_원장_차감안.xlsx")
    print("저장", BASE / "output" / "10월_원장_차감안.xlsx")


if __name__ == "__main__":
    main()
