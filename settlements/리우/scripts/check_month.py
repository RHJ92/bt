# 포장보스(리우) 본부수익금 월 마감 검증 — 관리자 화면 엑셀 2개(본부수익금 신청 + 주문 정산 내역)를 대조해 검토 초안 출력
# 실행: python -X utf8 check_month.py <브랜드> <YYYY-MM> <본부수익금신청.xlsx> <주문정산내역.xlsx>
#   예) python -X utf8 check_month.py 옥된장 2026-10 ../statements/261104_옥된장_10월_본부수익금신청.xlsx ../statements/261104_옥된장_10월_주문정산내역.xlsx
# 받는 법 (2026-11-04 정리): admin.pojangboss.com 로그인 → 브랜드 선택
#   ① 본부수익금 신청: /hq/settlement/mileage?statDateFrom=YYYY-MM&statDateTo=YYYY-MM → 「엑셀 출력」
#   ② 주문 정산 내역: /orders/sales/for-hq/boss?eventedAtFrom=YYYY-MM-01&eventedAtTo=YYYY-MM-말일 → 「조회」 → 「엑셀 출력」
# 판정 기준은 settlements/리우/README.md 「공급가 기준」: 냅킨 가맹점가 50,000 고정 / 물티슈 5% / 그 외 3% / 손잡이봉투 0%(본사 제안, 11월 이후도 0 정상)

import sys
from collections import defaultdict

import pandas as pd

MARGIN_OK = 0.029  # 3% 기준 — 원단위 반올림 차(±수십 원)는 정상으로 봄


def standard(name, code=""):
    """품목별 기준 마진 — (기준 설명, 최소 마진율 또는 None=별도 판정)"""
    if code.startswith("BOSSMRKT"):  # 포장보스 일반몰 상품 — 브랜드 전용가가 아니라 본사 마진 없음(적립 2%)이 정상 (정백선 9월·옥된장 10월 선례)
        return "일반몰 상품 (마진 없음 정상)", 0.0
    if "냅킨" in name:
        return "냅킨 가맹점가 50,000 고정", None
    if "물티슈" in name:
        return "물티슈 5%", 0.049
    if "손잡이 비닐봉투" in name:
        return "손잡이봉투 0% (본사 제안 단계 적용)", 0.0
    return "3%", MARGIN_OK


def load_detail(path, month):
    x = pd.read_excel(path, header=1)
    x.columns = [str(c).split("\r")[0].split("_x000d_")[0].strip() for c in x.columns]
    y, m = month.split("-")
    x = x[(x["연도"].astype(str) == y) & (x["월"].astype(str).str.zfill(2) == m)]  # 2024년 1~2월 과거 거래 섞임 방지
    return x


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return 0.0


def main(brand, month, req_path, det_path):
    req = pd.read_excel(req_path, header=1)
    req.columns = [str(c).split("_x000d_")[0].split("\n")[0].strip() for c in req.columns]
    row = req[req["구분"].astype(str) == month]
    if row.empty:
        sys.exit(f"신청 파일에 {month} 행이 없음")
    r = row.iloc[0]
    d = load_detail(det_path, month)
    sale, buy = d["매장 판매총액"].map(num).sum(), d["가맹본부 판매총액"].map(num).sum()
    profit = d["본부수익금"].map(num).sum()
    out = [f"**{brand} {month} 본부수익금 검증** (자동 초안 · check_month.py)", ""]
    out += ["**① 신청 요약 ↔ 주문 건별 합계**", "", "| 항목 | 신청 화면 | 건별 합계 | 차이 |", "|---|---:|---:|---:|"]
    for label, a, b in [("매출(매장 판매총액)", num(r["매출"]), sale), ("매입(가맹본부 판매총액)", num(r["매입"]), buy),
                        ("본부수익금 공급가액", num(r["공급가액"]), profit)]:
        out.append(f"| {label} | {a:,.0f} | {b:,.0f} | {a - b:,.0f} |")
    tax, total, etc, pay = (num(r[k]) for k in ("세액", "합계금액", "기타 비용", "지급 확정 금액"))
    out += ["", f"- 세액 {tax:,.0f} (공급가액×10% = {num(r['공급가액']) * 0.1:,.1f}) · 합계 {total:,.0f} · 기타 비용 {etc:,.0f} · **지급 확정 {pay:,.0f}**",
            f"- 신청 화면 반품배송비 {num(r.get('반품배송비', 0)):,.0f} · 배송비 {num(r.get('배송비', 0)):,.0f} · PG 수수료 {num(r.get('PG 결제 수수료', 0)):,.0f} · 상태 {r.get('상태', '')}",
            f"- 건수 {len(d)} · 매출기준일 {d['매출기준일'].min()} ~ {d['매출기준일'].max()}", ""]
    # 행별 산식
    bad = d[(d["매장 판매총액"].map(num) - d["가맹본부 판매총액"].map(num) - d["본부수익금"].map(num)).abs() > 1]
    out.append(f"- 행별 「매장 판매총액 − 가맹본부 판매총액 = 본부수익금」 불일치 {len(bad)}건" + "".join(
        f"\n  - {x['매출기준일']} {x['매장명']} {x['상품명']} ({x['상품코드']}): 차액 {num(x['매장 판매총액']) - num(x['가맹본부 판매총액']):,.0f} 중 "
        f"수익금 {num(x['본부수익금']):,.0f} (적립율 {x.get('적립율(%)', '')}%)" for _, x in bad.iterrows()))
    out.append(f"- 매출 − 매입 {sale - buy:,.0f} vs 본부수익금 {profit:,.0f} → 차이 {sale - buy - profit:,.0f} (위 불일치 행 합계와 같아야 함)")
    # 상품별 마진
    g = defaultdict(lambda: {"qty": 0, "buy": 0, "sale": 0, "profit": 0, "hq": set(), "store": set(), "code": ""})
    for _, x in d.iterrows():
        k = g[x["상품명"]]
        k["code"] = str(x["상품코드"])
        k["qty"] += num(x["주문/환불 수량"]); k["buy"] += num(x["가맹본부 판매총액"]); k["sale"] += num(x["매장 판매총액"])
        k["profit"] += num(x["본부수익금"]); k["hq"].add(num(x["가맹본부 단가"])); k["store"].add(num(x["매장 판매가"]))
    out += ["", "**② 상품별 마진**", "", "| 상품 | 수량 | 가맹본부가 | 판매가 | 본부수익금 | 마진율 | 판정 |", "|---|---:|---:|---:|---:|---:|---|"]
    flags = []
    for name, k in sorted(g.items(), key=lambda t: -t[1]["profit"]):
        rate = k["profit"] / k["buy"] if k["buy"] else 0
        std, need = standard(name, k["code"])
        if need is None:
            ok = all(s == 50000 for s in k["store"])
        else:
            ok = rate >= need - 1e-9
        mark = ("정상" + (f" · {std}" if need == 0.0 else "")) if ok else f"⚠️ 기준 미달({std})"
        if not ok:
            rows = d[d["상품명"] == name]
            by_date = "; ".join(f"{x['매출기준일']} {num(x['가맹본부 단가']):,.0f}→{num(x['매장 판매가']):,.0f}×{num(x['주문/환불 수량']):g}"
                                for _, x in rows.iterrows())
            flags.append(f"{name}: 마진 {rate:.2%} — 기준 {std}. 수량 {k['qty']:g} · 3% 적용 시 미발생액 약 "
                         f"{k['buy'] * 0.03 - k['profit']:,.0f}원\n  - 날짜별(가맹본부가→판매가×수량): {by_date}")
        hq = "/".join(f"{v:,.0f}" for v in sorted(k["hq"])); st = "/".join(f"{v:,.0f}" for v in sorted(k["store"]))
        out.append(f"| {name} | {k['qty']:g} | {hq} | {st} | {k['profit']:,.0f} | {rate:.2%} | {mark} |")
    # 환불·도서산간·기타
    refund = d[d["주문/환불 수량"].map(num) < 0]
    island = d["도서산간 추가 배송비"].map(num).sum() if "도서산간 추가 배송비" in d else 0
    out += ["", "**③ 수량·부대비용**", "", f"- 환불 {len(refund)}건" + "".join(
        f"\n  - {x['매출기준일']} {x['매장명']} {x['상품명']} {num(x['주문/환불 수량']):g} → 수익금 {num(x['본부수익금']):,.0f}" for _, x in refund.iterrows()),
        f"- 도서산간 추가 배송비 {island:,.0f} — 가맹점 부담, 정산 무관",
        f"- 기타 비용 {etc:,.0f}" + (" — **항목별 근거 요청 필요**" if etc else ""), ""]
    # ⑤ 단가 변동 — 포장보스가 인상·인하를 수시로 해서(2026-11-04 사용자) 월중 변동 + 전월 대비를 매번 본다
    out += ["", "**⑤ 단가 변동 (월중·전월 대비)**", ""]
    prev = prev_prices(brand, month)
    moved = []
    for name, k in sorted(g.items()):
        rows = d[d["상품명"] == name].sort_values("매출기준일")
        pairs = []
        for _, x in rows.iterrows():
            p = (num(x["가맹본부 단가"]), num(x["매장 판매가"]))
            if not pairs or pairs[-1][1] != p:
                pairs.append((str(x["매출기준일"]), p))
        last = pairs[-1][1]
        before = prev.get(k["code"])
        if len(pairs) > 1 or (before and before != last):
            path = ([f"전월 {before[0]:,.0f}→{before[1]:,.0f}"] if before and before != pairs[0][1] else []) + \
                   [f"{dte} {h:,.0f}→{s:,.0f}" for dte, (h, s) in pairs]
            rate = (last[1] - last[0]) / last[0] if last[0] else 0
            std, need = standard(name, k["code"])
            ok = (need is None and last[1] == 50000) or (need is not None and rate >= need - 1e-9)
            moved.append(f"- {name}: {' / '.join(path)} (가맹본부가→판매가) · 현재 수수료 {rate:.2%} — "
                         + ("기준 유지" if ok else f"⚠️ 기준 미달({std})"))
    out += moved or ["- 변동 없음" + ("" if prev else " (전월 단가 이력 없음 — 이번 달부터 쌓임)")]
    out += ["", "**④ 확인 필요**", ""] + ([f"- {f}" for f in flags] or ["- 없음"])
    print("\n".join(out))
    save_prices(brand, month, d, g)


LEDGER = __import__("pathlib").Path(__file__).resolve().parents[1] / "reference" / "단가이력.csv"


def prev_prices(brand, month):
    """단가이력.csv 에서 이 브랜드의 직전 달 마지막 단가 → {상품코드: (가맹본부가, 판매가)}"""
    if not LEDGER.exists():
        return {}
    h = pd.read_csv(LEDGER, dtype=str)
    h = h[(h["브랜드"] == brand) & (h["월"] < month)]
    if h.empty:
        return {}
    h = h[h["월"] == h["월"].max()]
    return {r["상품코드"]: (float(r["가맹본부가"]), float(r["판매가"])) for _, r in h.iterrows()}


def save_prices(brand, month, d, g):
    """이번 달 상품별 마지막 단가를 단가이력.csv 에 기록 (같은 브랜드·월은 덮어씀)"""
    rows = []
    for name, k in g.items():
        x = d[d["상품명"] == name].sort_values("매출기준일").iloc[-1]
        hq, st = num(x["가맹본부 단가"]), num(x["매장 판매가"])
        rows.append({"브랜드": brand, "월": month, "상품코드": k["code"], "상품명": name, "가맹본부가": hq, "판매가": st,
                     "수수료율": round((st - hq) / hq, 4) if hq else 0, "마지막 매출기준일": x["매출기준일"]})
    new = pd.DataFrame(rows)
    if LEDGER.exists():
        old = pd.read_csv(LEDGER, dtype=str)
        new = pd.concat([old[~((old["브랜드"] == brand) & (old["월"] == month))], new.astype(str)])
    LEDGER.parent.mkdir(exist_ok=True)
    new.sort_values(["브랜드", "월", "상품코드"]).to_csv(LEDGER, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__ or "사용법: check_month.py 브랜드 YYYY-MM 신청.xlsx 주문정산.xlsx")
    main(*sys.argv[1:])
