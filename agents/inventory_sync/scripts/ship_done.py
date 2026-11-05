# 「보냄」이 끝난 주문 → 마켓봄 출고완료 처리 (2026-11-04 사용자 지시 「주문서 확인 후 보내기 누른 건은 출고완료 처리까지」)
# 실행: python -X utf8 ship_done.py 주문번호 [주문번호 ...]
# 봇의 「📨 보냄」 버튼이 그 주문의 모든 출고처가 보냄이 됐을 때 부른다 — 사람이 따로 부를 일은 거의 없음
# 안전장치: 출고전(OS001)인 주문만 요청, 요청 뒤 목록을 다시 읽어 출고완료(OS002)로 바뀐 것만 「완료」로 보고
# 계정(9517·3802·10509) 중 그 주문번호가 보이는 계정에서 처리. 결과는 ../state/shipped.json 에 남김
# 디자인물만인 출고전 주문은 주문서·「보냄」이 없어 계속 출고전으로 남으므로 출고완료를 할 때 같이 넣는다 (사용자 지시 2026-11-05)

import datetime as dt
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

import classify
import fetch_orders
import marketbom as mb
import orders_read

STATE = Path(__file__).resolve().parents[1] / "state"
SHIPPED = STATE / "shipped.json"
STATUS = {"OS001": "출고전", "OS002": "출고완료", "OS003": "출고거절", "OS004": "주문취소", "OS005": "반품접수", "OS006": "반품완료"}


DESIGN_LOOKBACK = 30


def design_only(today):
    """출고전 주문 중 **구매팀 출고가 없는 디자인물 주문**(디자인물, 또는 디자인물+배송비만) → {주문번호: 설명}.
    주문서가 안 나가는 줄이라 「보냄」이 없고 계속 출고전으로 남는다 → 출고완료 때 같이 처리 (사용자 지시 2026-11-05).
    구매팀 품목이 섞인 주문은 넣지 않는다 — 그 주문은 보냄 경로로만 (실물이 아직 안 나갔을 수 있음)"""
    rows = [r for p in fetch_orders.fetch(str(today - dt.timedelta(days=DESIGN_LOOKBACK)),
                                          str(today + dt.timedelta(days=14)), "OS001").values()
            for r in orders_read.read(p)]
    group = {}
    for r in rows:
        v, note = classify.vendor_of(r)
        group.setdefault(str(r["주문번호"]), []).append((note if v is None else v, r))
    out = {}
    for num, items in group.items():
        kinds = {k for k, _ in items}
        if kinds <= {"디자인물", "배송비"} and "디자인물" in kinds:
            r0 = items[0][1]
            out[num] = f"디자인물 {len(items)}행 · {r0['거래처']} · 배송요청 {r0['배송요청일']}"
    return out


def main(wanted):
    today = dt.date.today()
    extra = {o: why for o, why in design_only(today).items() if o not in wanted}
    wanted = list(wanted) + sorted(extra)
    sdate, edate = f"{today - dt.timedelta(days=31):%Y-%m-%d}", f"{today + dt.timedelta(days=7):%Y-%m-%d}"
    result, left = {}, list(wanted)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        try:
            for acc in mb.ACCOUNTS:
                if not left:
                    break
                ctx = browser.new_context()
                ok, why = mb.saved_login(ctx.new_page(), acc)
                if not ok:
                    for o in left:
                        result.setdefault(o, f"⚠️ {acc} 로그인 실패 — {why}")
                    continue
                found = {o: v for o, v in mb.order_ids(ctx, sdate, edate).items() if o in left}
                go = [o for o, (_, st) in found.items() if st == "OS001"]
                for o, (_, st) in found.items():
                    if st != "OS001":
                        result[o] = f"이미 {STATUS.get(st, st)} — 요청 안 함"
                if go:
                    code = mb.ship_done(ctx, [found[o][0] for o in go])
                    after = mb.order_ids(ctx, sdate, edate)
                    for o in go:
                        st = after.get(o, (None, "?"))[1]
                        result[o] = "✅ 출고완료" if st == "OS002" else f"⚠️ 요청 결과 {code}, 지금 상태 {STATUS.get(st, st)}"
                left = [o for o in left if o not in found]
                ctx.close()
        finally:
            browser.close()
    for o in left:
        result[o] = "⚠️ 세 계정 어디에도 이 주문번호가 없음 (최근 31일)"
    log = json.loads(SHIPPED.read_text(encoding="utf-8")) if SHIPPED.exists() else []
    log += [{"주문번호": o, "결과": r, "시각": f"{dt.datetime.now():%Y-%m-%d %H:%M}"} for o, r in result.items()]
    STATE.mkdir(exist_ok=True)
    SHIPPED.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    for o in wanted:
        print(f"• {o}: {result[o]}" + (f" (디자인물 — 주문서 없이 같이 처리: {extra[o]})" if o in extra else ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main([a for a in sys.argv[1:] if a])
