# 에이엠비 재고수불 사이트 계정 저장 + 로그인 시험
# 실행: python "C:\Users\BLUETREND\류호정\bt\agents\expense_report\scripts\set_wms_password.py"
# 아이디 → 엔터 → 비밀번호(화면에 안 보이는 게 정상) → 엔터

import getpass
import json

import keyring

from wms_amb import CONFIG, KEYRING_SERVICE, try_login

while True:
    user_id = input("아이디만 입력: ").strip()
    pw = getpass.getpass("비밀번호 (입력해도 안 보임): ")
    if try_login(user_id, pw):
        keyring.set_password(KEYRING_SERVICE, user_id, pw)
        CONFIG.write_text(json.dumps({"id": user_id}), encoding="utf-8")
        print("로그인 성공 — 저장했습니다. 이제 창을 닫으셔도 됩니다.")
        break
    print("로그인 실패 — 저장 안 함. 다시 입력하세요.\n")
