# 유니폼 선분출 폼 응답 → 신청 탭 (품목 1개당 1줄). 재고 화면 새로고침 때 실행
# 응답 수정은 상태가 빈 줄에만 반영, 구매팀이 상태를 넣은 줄은 건드리지 않음

import json
import re
from pathlib import Path

import requests

STATE = Path(__file__).resolve().parents[1] / "state" / "preship_sheet.json"
API = "https://sheets.googleapis.com/v4/spreadsheets"
RESP = "설문지 응답 시트1"
SLOTS = 5
KEY_COL = 14  # O 응답번호 (응답 행-품목 칸)
STATE_COL = 9  # J 상태


def get(tok, sid, rng):
    r = requests.get(f"{API}/{sid}/values/{requests.utils.quote(rng)}", headers={"Authorization": "Bearer " + tok},
                     params={"valueRenderOption": "UNFORMATTED_VALUE"}, timeout=60)
    r.raise_for_status()
    return r.json().get("values", [])


def split(resp):
    """응답 행(가로) → {응답번호: 신청 A~I}. 품목을 지운 칸은 빈 줄"""
    out = {}
    for i, r in enumerate(resp, 2):
        r = (list(r) + [""] * 17)[:17]
        for k in range(SLOTS):
            item, qty = r[5 + 2 * k], r[6 + 2 * k]
            if isinstance(qty, str) and qty.strip().isdigit():
                qty = int(qty)
            out[f"{i}-{k + 1}"] = [r[0], r[1], r[2], r[3], item, qty, r[4], r[15], r[16]] if item else [""] * 9
    return out


def sync(tok, resp=None):
    sid = json.loads(STATE.read_text(encoding="utf-8"))["id"]
    h = {"Authorization": "Bearer " + tok}
    if resp is None:
        resp = get(tok, sid, f"'{RESP}'!A2:Q")
    have = [(list(r) + [""] * (KEY_COL + 1))[:KEY_COL + 1] for r in get(tok, sid, "신청!A3:O1000")]
    keys = {r[KEY_COL]: (n, r) for n, r in enumerate(have, 3) if r[KEY_COL]}
    data, row = [], 3 + len(have)
    for key, cells in split(resp).items():
        if key in keys:
            n, old = keys[key]
            if not str(old[STATE_COL]).strip() and old[:9] != cells:
                data.append({"range": f"신청!A{n}:I{n}", "values": [cells]})
        elif cells[4]:
            data.append({"range": f"신청!A{row}:I{row}", "values": [cells]})
            data.append({"range": f"신청!O{row}", "values": [[key]]})
            row += 1
    if data:
        requests.post(f"{API}/{sid}/values:batchUpdate", headers=h, timeout=60,
                      json={"valueInputOption": "RAW", "data": data}).raise_for_status()
    return len(data)


def open_requests(tok):
    """취소 아닌 신청 줄 → [{매장, 품목, 수량, 주문번호}]. 폼 응답을 먼저 옮긴 뒤 읽는다"""
    sync(tok)
    sid = json.loads(STATE.read_text(encoding="utf-8"))["id"]
    out = []
    for r in get(tok, sid, "신청!A3:O1000"):
        r = (list(r) + [""] * 15)[:15]
        if str(r[3]).strip() and str(r[4]).strip() and str(r[STATE_COL]).strip() != "취소":
            out.append({"매장": str(r[3]).strip(), "품목": str(r[4]).strip(), "수량": r[5], "주문번호": str(r[12]).strip()})
    return out


def link_orders(tok, pairs):
    """확실히 맞은 (매장, 품목, 주문번호) → 신청 탭 M(마켓봄 주문번호)가 빈 줄에 기록. 이상 감지 「분출 후 주문 없음」이 풀린다"""
    if not pairs:
        return 0
    sid = json.loads(STATE.read_text(encoding="utf-8"))["id"]
    data = []
    for n, r in enumerate(get(tok, sid, "신청!A3:O1000"), 3):
        r = (list(r) + [""] * 15)[:15]
        for shop, code, oid in pairs:
            if _shop(r[3]) == _shop(shop) and str(r[4]).strip() == code and not str(r[12]).strip() and str(r[STATE_COL]).strip() != "취소":
                data.append({"range": f"신청!M{n}", "values": [[oid]]})
    if data:
        requests.post(f"{API}/{sid}/values:batchUpdate", headers={"Authorization": "Bearer " + tok}, timeout=60,
                      json={"valueInputOption": "RAW", "data": data}).raise_for_status()
    return len(data)


def _shop(s):
    return re.sub(r"\s|\(주\)|옥된장|석문어|정백선|점$", "", str(s))


def match(order, code, qty, reqs):
    """경인양행으로 갈 유니폼 주문 한 줄 → (판정, 사유). 판정: None(선분출 무관) / "제외"(확실한 선분출 건) / "확인"(헷갈림)"""
    oid, shop = order["주문번호"], str(order["거래처"])
    if any(q["주문번호"] == oid for q in reqs):
        same = [q for q in reqs if q["주문번호"] == oid and q["품목"] == code]
        return ("제외", "선분출 신청에 이 주문번호가 적혀 있음") if same else ("확인", "선분출 신청에 이 주문번호가 있지만 품목이 다름")
    open_reqs = [q for q in reqs if not q["주문번호"]]
    if "에프엔비" in shop:
        return ("확인", "본사 대리 주문 — 열린 선분출 신청이 있어 매장 확인 필요") if open_reqs else (None, "")
    exact = [q for q in open_reqs if _shop(q["매장"]) == _shop(shop)]
    near = [q for q in open_reqs if q not in exact and _shop(q["매장"]) and
            (_shop(q["매장"]) in _shop(shop) or _shop(shop) in _shop(q["매장"]))]
    if near:
        return "확인", f"선분출 신청 매장명 「{near[0]['매장']}」과 비슷함"
    if not exact:
        return None, ""
    same = [q for q in exact if q["품목"] == code]
    if not same:
        return "확인", f"이 매장 선분출 신청이 있지만 {code}는 신청에 없음"
    asked = sum(float(q["수량"] or 0) for q in same)
    if asked != qty:
        return "확인", f"선분출 신청 {asked:g}개 · 주문 {qty:g}개로 수량이 다름"
    return "제외", f"선분출 신청과 매장·품목·수량 일치 ({asked:g}개)"
