# 포장보스 관리자 계정 저장 + 로그인 시험 (호정님이 직접 실행 — 비밀번호는 채팅·파일에 남기지 않음)
# 실행: python "C:\Users\BLUETREND\류호정\bt\settlements\리우\scripts\set_pojangboss_password.py"
# 아이디 → 엔터 → 비밀번호(화면에 안 보이는 게 정상) → 엔터. 로그인에 성공해야만 저장한다

import getpass
import json

import keyring
from playwright.sync_api import sync_playwright

from pojangboss import CONFIG, KEYRING_SERVICE, load_id, login

saved = load_id()
print("[포장보스 관리자]" + (f" (저장된 아이디 {saved} — 그대로 두려면 엔터)" if saved else ""))
user_id = input("  아이디만 입력: ").strip() or saved
if not user_id:
    raise SystemExit("  아이디가 없어 종료")
pw = getpass.getpass("  비밀번호 (입력해도 안 보임): ")
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    page = b.new_page()
    page.on("dialog", lambda d: d.dismiss())
    ok, why = login(page, user_id, pw)
    b.close()
if ok:
    keyring.set_password(KEYRING_SERVICE, user_id, pw)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"id": user_id}), encoding="utf-8")
    print("  로그인 성공 — 저장했습니다.")
else:
    print("  저장 안 함 —", why)
input("\n엔터를 누르면 창이 닫힙니다.")
