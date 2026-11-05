# 포장보스 관리자(admin.pojangboss.com) 로그인 — 아이디·비밀번호만, 문자·캡차 없음 (2026-11-05 확인)
# 아이디는 agents/shared/config/pojangboss.json(깃 미추적), 비밀번호는 Windows 자격 증명 관리자 "pojangboss"
# 등록: python -X utf8 set_pojangboss_password.py (호정님이 직접 실행 — 비밀번호는 채팅에 쓰지 않음)
# 한 계정으로 브랜드 4개(옥된장·석문어·정백선·육직구)를 화면 왼쪽 아래 「브랜드 변경」으로 오간다

import json
from pathlib import Path

import keyring

BASE = "https://admin.pojangboss.com"
KEYRING_SERVICE = "pojangboss"
CONFIG = Path(__file__).resolve().parents[3] / "agents" / "shared" / "config" / "pojangboss.json"


def login(page, user_id, password):
    """→ (성공 여부, 사유)"""
    page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
    page.fill("input[placeholder*='아이디']", user_id)
    page.fill("input[type=password]", password)
    page.get_by_role("button", name="로그인").last.click()
    page.wait_for_timeout(5000)
    if page.locator("input[type=password]:visible").count():
        text = page.inner_text("body")
        return False, "로그인 화면 그대로 — " + next((l for l in text.splitlines() if "비밀번호" in l or "일치" in l), "아이디·비밀번호 확인")
    return True, ""


def load_id():
    return json.loads(CONFIG.read_text(encoding="utf-8")).get("id") if CONFIG.exists() else None


def saved_login(page):
    user_id = load_id()
    if not user_id or not keyring.get_password(KEYRING_SERVICE, user_id):
        return False, "포장보스 계정 미등록 — settlements/리우/scripts/set_pojangboss_password.py 를 호정님이 실행"
    return login(page, user_id, keyring.get_password(KEYRING_SERVICE, user_id))


def save_state(context):
    """로그인된 쿠키를 파일로 — 다음 실행은 로그인 없이 (state/ 는 깃 미추적)"""
    path = CONFIG.parent.parent / "slack_bot" / "state" / "pojangboss_session.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(path))
    return path
