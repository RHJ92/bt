# 매일 09:00: 3개 계정 출고전 주문 → 출고처별 분류 + 주문서 파일 → 봇이 #마켓봄_주문_출고관리에 파일·「보냄」 버튼 게시
# 실행: python -X utf8 daily_orders.py   (마켓봄·시트에 쓰지 않음. 파일은 ../output/YYMMDD/, 묶음 정보는 ../state/batches/)
# 주문 마감 오전 9시: 그 뒤에 들어온 주문은 다음 영업일 차례 (사용자 지시 2026-11-02)
# 한 주문번호가 두 출고처로 나뉘면 양쪽 다 「보냄」이 된 뒤에 출고완료 대상이 된다 (사용자 지시 2026-11-02)
# 이미 보낸 (주문번호, 출고처)는 ../state/sent.json 에 남아 다음 날 출고전으로 또 보여도 주문서를 다시 만들지 않는다

import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path

import classify
import fetch_orders
import ledger_october as lo
import ledger_preview as lp
import make_requests
import orders_read
import preship_sync

LOOKBACK_DAYS = 14
SHEET = "1DfGgHvHuecTGySam_TiNusUtohKFwGB4AtYG_8K_ErQ"
STATE = Path(__file__).resolve().parents[1] / "state"
SENT = STATE / "sent.json"


def main():
    today = dt.date.today()
    paths = fetch_orders.fetch(str(today - dt.timedelta(days=LOOKBACK_DAYS)), str(today + dt.timedelta(days=14)), "OS001")
    cutoff = f"{today:%Y-%m-%d} 09:00:00"
    all_rows = [r for p in paths.values() for r in orders_read.read(p)]
    rows = [r for r in all_rows if str(r["주문일시"]) < cutoff]
    late = len(all_rows) - len(rows)
    sent = set(map(tuple, json.loads(SENT.read_text(encoding="utf-8")))) if SENT.exists() else set()

    # 유니폼 선분출 신청이 있는 주문은 경인양행 주문서에 넣지 않는다. 애매하면 확인 필요로 묻는다 (사용자 지시 2026-11-03)
    tok = lp.g_token(True)
    by_code, by_name = lp.masters(tok, SHEET)
    reqs = preship_sync.open_requests(tok)
    preshipped, links = [], []
    # 티타늄 삼보 잔량 = 원장 잔량 − 이미 삼보로 보냈지만 아직 출고전인 주문 (원장에 아직 안 빠짐)
    left = lo.titanium_left(tok, SHEET)
    for r in rows:
        code = lo.item_code(r, by_code, by_name)
        if code in left and (r["주문번호"], "삼보물류") in sent:
            left[code] -= classify.ship_qty(r, "삼보물류")
    split = []

    by_vendor, unknown, order_vendors, skipped, already = defaultdict(list), [], defaultdict(set), 0, 0
    for r in rows:
        v, note = classify.vendor_of(r)
        if v == "경인양행" and (r["주문번호"], v) not in sent:
            m = by_code.get(str(r["상품코드"]).strip().removesuffix(".0")) or by_name.get(re.sub(r"\s+", "", str(r["상품명"])))
            code, qty = None, 0
            if m:
                code, qty = m["품목코드"], classify.ship_qty(r, v)
            elif "모자 3ea" in str(r["상품명"]):
                code, qty = "옥된장 모자", r["수량"] * 3
            if code:
                verdict, why = preship_sync.match(r, code, qty, reqs)
            else:
                verdict, why = ("확인", "품목 마스터에 없는 유니폼") if reqs else (None, "")
            if verdict == "제외":
                preshipped.append((r, why))
                links.append((r["거래처"], code, r["주문번호"]))
                order_vendors[r["주문번호"]].add("선분출")
                continue
            if verdict == "확인":
                v, note = "확인 필요", f"선분출 확인 — {why}. 경인양행 주문서에 넣을지 알려 주세요"
        parts = [(v, r)]
        code = lo.item_code(r, by_code, by_name) if v == "삼보물류" else None
        if code in left and (r["주문번호"], "삼보물류") not in sent:
            # 삼보 잔량을 먼저 소진하고 모자라는 만큼 명화주방 주문서로 나눈다 (사용자 지시 2026-11-03)
            qty = classify.ship_qty(r, v)
            per = qty / r["수량"] if r["수량"] else 1
            parts = [(w, {**r, "수량": q / per if w == "삼보물류" else q}) for w, q in classify.split_titanium(qty, left[code])]
            left[code] = max(0, left[code] - qty)
            if len(parts) > 1:
                split.append((r, parts))
        for v, r in parts:
            if v is None:
                skipped += 1
            elif v == "확인 필요":
                unknown.append((r, note))
                order_vendors[r["주문번호"]].add("확인 필요")
            elif (r["주문번호"], v) in sent:
                already += 1
                order_vendors[r["주문번호"]].add(v)
            else:
                by_vendor[v].append(r)
                order_vendors[r["주문번호"]].add(v)

    made, missing = make_requests.build(by_vendor, today)
    for r in missing:
        order_vendors[r["주문번호"]].add("확인 필요")

    print(f"*{today:%m/%d} 출고전 주문* — 3개 계정 {len(rows)}행 · 구매팀 대상 아님 {skipped}행"
          + (f" · 09:00 이후 주문 {late}행은 다음 영업일" if late else "")
          + (f" · 이미 보낸 {already}행 제외" if already else ""))
    vendors = {}
    for v, items in by_vendor.items():
        keep = [r for r in items if r not in missing]
        if v not in made:
            continue
        print(f"• {v}: {len({r['주문번호'] for r in keep})}주문 {len(keep)}행 · 수량 {sum(classify.ship_qty(r, v) for r in keep):g}")
        for r in keep[:20]:
            print(f"   - [{r['계정']}] {r['거래처']} · {str(r['상품명'])[:30]} × {classify.ship_qty(r, v):g} · 배송요청 {r['배송요청일']}")
        vendors[v] = {"file": str(made[v]), "orders": sorted({r["주문번호"] for r in keep}), "rows": len(keep), "sent": False}
    for r, note in unknown:
        print(f"• ⚠️ 확인 필요: [{r['계정']}] {r['거래처']} · {str(r['상품명'])[:30]} × {r['수량']:g} · 배송요청 {r['배송요청일']} · {note}")
    for r in missing:
        print(f"• ⚠️ 확인 필요: [{r['계정']}] {r['거래처']} 배송지를 거래처 파일에서 못 찾음 — 거래처 파일을 새로 받아야 함")
    for r, parts in split:
        print(f"• 🍽 삼보·명화 나눔: [{r['계정']}] {r['거래처']} · {str(r['상품명'])[:30]} × {classify.ship_qty(r, '삼보물류'):g} → "
              + " / ".join(f"{w} {classify.ship_qty(x, w):g}" for w, x in parts) + " (삼보 잔량 소진)")
    for r, why in preshipped:
        print(f"• 🎽 선분출 건 — 경인양행 주문서에서 뺌: [{r['계정']}] {r['거래처']} · {str(r['상품명'])[:30]} × {r['수량']:g} · {why}")
    if links:
        print(f"• 선분출 신청 시트에 마켓봄 주문번호 {preship_sync.link_orders(tok, links)}칸 기록")

    STATE.joinpath("batches").mkdir(parents=True, exist_ok=True)
    batch = STATE / "batches" / f"{today:%y%m%d}.json"
    batch.write_text(json.dumps({"date": str(today), "vendors": vendors,
                                 "orders": {o: sorted(v) for o, v in order_vendors.items()}},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    need = len(unknown) + len(missing)
    print(f"BATCH: {batch}")
    print(f"STATUS: 완료 · 출고전 {len(rows)}행 · 주문서 {len(vendors)}곳" + (f" · 확인 필요 {need}건" if need else ""))


if __name__ == "__main__":
    main()
