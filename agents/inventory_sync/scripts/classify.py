# 주문 한 줄 → 출고처. 규칙 원본: shipping_request/README.md 「업체 매칭표」 + 2026-11-02 사용자 지정. 표에 없으면 임의로 넣지 않고 "확인 필요"

import json
import re
from pathlib import Path

MANUAL = Path(__file__).resolve().parents[1] / "출고처_매뉴얼.json"
UNIFORM = ("유니폼", "모자")
HQ_ITEMS = ("물티슈", "수저봉투", "일회용앞치마")


def manual_rule(name, buyer):
    """사용자가 확인해 둔 규칙(출고처_매뉴얼.json) 중 첫 일치. 호출 때마다 읽어서 추가하면 바로 적용"""
    for rule in json.loads(MANUAL.read_text(encoding="utf-8"))["규칙"]:
        if rule["상품명"] in name and ("대표매입처" not in rule or rule["대표매입처"] == buyer):
            return rule
    return None


def vendor_of(r):
    """→ (출고처, 비고). 출고처 None = 구매팀 대상 아님(디자인물·배송비)"""
    name, buyer = str(r["상품명"]), str(r["대표 매입처"]).strip()
    if "배송비" in name:
        return None, "배송비"
    if "디자인_" in name or "_현수막" in name:
        return None, "디자인물"
    hit = manual_rule(name, buyer)
    if hit:
        return hit["출고처"], hit.get("비고") or (hit["유형"] if hit["출고처"] is None else "")
    if buyer == "천안축산물유통센터":
        return "천안축산물유통센터", ""
    if buyer == "가야김치":
        return "가야김치", ""
    if buyer == "찌개연구소":
        return "찌개연구소", ""
    if buyer == "옥된장 티타늄":
        return "삼보물류", "삼보 잔량 소진 후 명화주방 전환 — 재고 확인"
    if "쇼핑백" in name and not buyer:
        return "삼보물류", "대표 매입처 빈칸 — 삼보 보관 품목"
    if buyer == "블루트렌드":
        if any(w in name for w in UNIFORM):
            return "경인양행", ""
        if any(w in name for w in HQ_ITEMS):
            return "블루트렌드(본사)", "정백선 소모품"
    return "확인 필요", f"매뉴얼에 없음 (대표 매입처 {buyer or '빈칸'})"


def split_titanium(qty, left):
    """티타늄 한 줄 → [(출고처, 수량)]. 삼보 잔량을 먼저 소진하고 모자라는 만큼 명화주방 (사용자 지시 2026-11-03)"""
    if left >= qty:
        return [("삼보물류", qty)]
    if left <= 0:
        return [("명화주방", qty)]
    return [("삼보물류", left), ("명화주방", qty - left)]


def ship_qty(r, vendor):
    """삼보는 실제 출고 낱개 수 = 수량 × 단위의 ea 수 (단위 100ea·수량 1 → 100). 그 외 업체는 마켓봄 수량 그대로"""
    qty = float(r["수량"] or 0)
    m = re.fullmatch(r"(\d+)\s*ea", str(r["단위"]).strip(), re.I)
    return qty * int(m[1]) if vendor == "삼보물류" and m else qty
