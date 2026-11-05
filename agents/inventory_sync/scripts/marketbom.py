# 마켓봄(vendor.marketbom.com) 로그인 — 9517·3802·10509, 조회 전용 (주문·저장 버튼 안 누름)
# 쓰기는 출고완료 하나뿐 — ship_done.py 가 「보냄」 끝난 주문만 (2026-11-04 사용자 지시)
# 아이디는 shared/config/marketbom.json(깃 미추적), 비밀번호는 Windows 자격 증명 관리자 "marketbom"

import json
import re
from pathlib import Path

import keyring

LOGIN = "https://vendor.marketbom.com/vendor/dashboard"  # 비로그인이면 auth.marketbom.com/login/portal 로 보냄
KEYRING_SERVICE = "marketbom"
CONFIG = Path(__file__).resolve().parents[2] / "shared" / "config" / "marketbom.json"
VERIFY_WORDS = ("인증번호", "인증 번호", "OTP", "문자", "휴대폰 인증", "보안문자")


def login(page, user_id, password):
    """→ (성공 여부, 사유). 문자·OTP 화면이면 실패로 돌려주고 멈춤"""
    page.goto(LOGIN, wait_until="domcontentloaded", timeout=40000)
    page.wait_for_selector("input[type=password]", timeout=20000)
    page.locator("input[type=text]:visible").first.fill(user_id)
    page.locator("input[type=password]:visible").first.fill(password)
    page.get_by_role("button", name="로그인").first.click()
    page.wait_for_timeout(6000)
    text = page.inner_text("body")
    hit = [w for w in VERIFY_WORDS if w in text]
    if "vendor.marketbom.com" in page.url:
        return True, ""
    return False, f"추가 인증 화면으로 보임 {hit}" if hit else f"로그인 안 됨 ({page.url[:60]})"


ACCOUNTS = {"9517": "블루트렌드", "3802": "육직구삼겹", "10509": "철산장"}  # 계정마다 브라우저 context를 따로 쓴다


def load_ids():
    return json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}


def saved_login(page, account="9517"):
    user_id = load_ids()[account]
    return login(page, user_id, keyring.get_password(KEYRING_SERVICE, user_id))


BASE = "https://vendor.marketbom.com"
ORDER_FORM = {"page": "1", "order_by1": "desc", "period_type": "1", "search_type": "cg.goods_name",
              "order_list_cnt": "100"}


def order_ids(context, sdate, edate, status=""):
    """주문별 목록(/vendor/order/olist) → {주문번호: (내부 번호, 상태코드)}. 출고완료 요청은 내부 번호로 한다"""
    page = context.new_page()
    try:
        page.goto(BASE + "/vendor/order/olist?" + "&".join(f"{k}={v}" for k, v in {
            "page": "1", "period_type": "1", "order_list_cnt": "500", "sdate": sdate, "edate": edate,
            "order_status": status}.items()), wait_until="networkidle", timeout=60000)
        rows = page.evaluate("""()=>[...document.querySelectorAll('input[name=order_id]')].filter(i=>i.value)
            .map(i=>[i.value, i.getAttribute('order_status'), i.closest('tr').innerText])""")
    finally:
        page.close()
    out = {}
    for oid, st, text in rows:
        m = re.search(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\s+\d{4}-\d\d-\d\d\s+(\S+)", text)
        if m:
            out[m[1]] = (oid, st)
    return out


def ship_done(context, ids):
    """출고완료 처리 (화면 「출고 완료」 버튼 goDeliveryEnd 과 같은 요청).
    order_status OS001(출고전) + delivery_status OSD002 인 주문만 된다.
    result_code 00 성공 / 06 상태 불가 / 07 처리 불가 / 그 밖(01 등) 실패 — order_list.js 기준.
    **action=delivery_end 가 빠지면 01 로 떨어진다** (2026-11-05 확인)"""
    # 화면 안에서 jQuery 로 보낸다 — 화면에 걸린 공통 설정(헤더 등)을 그대로 타게
    page = context.new_page()
    try:
        page.goto(BASE + "/vendor/order/olist", wait_until="networkidle", timeout=60000)
        res = page.evaluate("""ids => new Promise(ok => $.ajax({type: 'POST', url: '/vendor/order/olist_proc2',
            data: 'action=delivery_end&order_ids=' + ids, dataType: 'json', success: d => ok(d), error: (x, s) => ok({result_code: 'ERR ' + x.status})}))""",
                            ",".join(ids))
    finally:
        page.close()
    return res.get("result_code")


def orders_excel(context, sdate, edate, status=""):
    """상품별주문목록 엑셀(.xls 원본 bytes) — 로그인된 브라우저 context 필요. status: OS001 출고전 / OS002 출고완료 등"""
    r = context.request.get(BASE + "/vendor/order/order_goods_list_excel", timeout=60000,
                            params={**ORDER_FORM, "sdate": sdate, "edate": edate, "order_status": status})
    if not r.ok or "excel" not in (r.headers.get("content-type") or ""):
        raise RuntimeError(f"주문목록 엑셀 실패 ({r.status}) — 세션 만료 또는 화면 변경")
    return r.body()
