# SWC 창고 재고수불 사이트 계정 저장 + 로그인 시험
# 실행: python "C:\Users\BLUETREND\류호정\bt\agents\expense_report\scripts\set_swc_password.py"

import getpass
import json

import keyring

from wms_amb import CONFIG_SWC, KEYRING_SWC, URL_SWC, try_login

while True:
    user_id = input("아이디만 입력: ").strip()
    pw = getpass.getpass("비밀번호 (입력해도 안 보임): ")
    if try_login(user_id, pw, URL_SWC):
        keyring.set_password(KEYRING_SWC, user_id, pw)
        CONFIG_SWC.write_text(json.dumps({"id": user_id}), encoding="utf-8")
        print("로그인 성공 — 저장했습니다. 이제 창을 닫으셔도 됩니다.")
        break
    print("로그인 실패 — 저장 안 함. 다시 입력하세요.")
