# 에이엠비(한솔냉장)·SWC 통합물류정보 로그인 — 재고수불 확인용 (조회 전용, 출고요청·저장 버튼은 누르지 않음)
# 주소는 http만 열린다 (443 닫힘, 2026-11-02 확인)
# 아이디는 shared/config/wms_amb.json(깃 미추적), 비밀번호는 Windows 자격 증명 관리자 "amb-wms"

import json
from pathlib import Path

import keyring
from playwright.sync_api import sync_playwright

URL = "http://211.239.173.90/unddst/login.do"
KEYRING_SERVICE = "amb-wms"
CONFIG = Path(__file__).resolve().parents[2] / "shared" / "config" / "wms_amb.json"
URL_SWC = "http://nwill.net:8080/nswdst/login.do"
KEYRING_SWC = "swc-wms"
CONFIG_SWC = Path(__file__).resolve().parents[2] / "shared" / "config" / "wms_swc.json"


def login(page, user_id, password, url=URL):
    """성공하면 True — 로그인 칸이 사라졌는지로 판단. SWC 창고도 같은 시스템이라 url만 다름"""
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    pw = page.locator("input[type=password]:visible").first
    page.locator("input[type=text]:visible:not(#top-search)").first.fill(user_id)
    pw.fill(password)
    pw.press("Enter")
    page.wait_for_timeout(4000)
    return page.locator("input[type=password]:visible").count() == 0


def saved_login(page):
    user_id = json.loads(CONFIG.read_text(encoding="utf-8"))["id"]
    return login(page, user_id, keyring.get_password(KEYRING_SERVICE, user_id))


def saved_login_swc(page):
    user_id = json.loads(CONFIG_SWC.read_text(encoding="utf-8"))["id"]
    return login(page, user_id, keyring.get_password(KEYRING_SWC, user_id), URL_SWC)


def try_login(user_id, password, url=URL):
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        try:
            page = b.new_page()
            page.on("dialog", lambda d: d.dismiss())
            return login(page, user_id, password, url)
        finally:
            b.close()
