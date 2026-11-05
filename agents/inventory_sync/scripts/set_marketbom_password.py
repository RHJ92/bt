# 마켓봄 계정 저장 + 로그인 시험 (9517·3802·10509). 문자·OTP가 뜨면 저장하지 않고 멈춤
# 실행: python "C:\Users\BLUETREND\류호정\bt\agents\inventory_sync\scripts\set_marketbom_password.py"
# 계정마다: 아이디 → 엔터 → 비밀번호(화면에 안 보이는 게 정상) → 엔터. 이미 저장된 계정은 아이디 칸에서 그냥 엔터

import getpass
import json

import keyring
from playwright.sync_api import sync_playwright

from marketbom import ACCOUNTS, CONFIG, KEYRING_SERVICE, load_ids, login

for account, name in ACCOUNTS.items():
    saved = load_ids().get(account)
    print(f"\n[{account} {name}]" + (" (저장됨 — 그대로 두려면 엔터)" if saved else ""))
    user_id = input("  아이디만 입력: ").strip()
    if not user_id:
        print("  건너뜀")
        continue
    pw = getpass.getpass("  비밀번호 (입력해도 안 보임): ")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        page = b.new_page()
        page.on("dialog", lambda d: d.dismiss())
        ok, why = login(page, user_id, pw)
        b.close()
    if ok:
        keyring.set_password(KEYRING_SERVICE, user_id, pw)
        ids = load_ids()
        ids[account] = user_id
        CONFIG.write_text(json.dumps(ids), encoding="utf-8")
        print("  로그인 성공 — 저장했습니다.")
    else:
        print("  저장 안 함 —", why)
