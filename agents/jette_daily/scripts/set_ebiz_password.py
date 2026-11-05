# 제때 ebiz 계정 저장 + 로그인 시험 — 옥된장·철산장 두 계정을 차례로 묻는다
# 실행: python "C:\Users\BLUETREND\류호정\bt\agents\jette_daily\scripts\set_ebiz_password.py"
# 한 줄에 한 가지만 입력: 아이디 → 엔터 → 비밀번호(화면에 안 보이는 게 정상) → 엔터
# 아이디는 shared/config/jette_accounts.json(깃 미추적), 비밀번호는 Windows 자격 증명 관리자 "jette-ebiz"

import getpass

import keyring

from ebiz import KEYRING_SERVICE, Ebiz, load_accounts, save_account

for alias in ("옥된장", "철산장"):
    saved = load_accounts().get(alias)
    print(f"\n[{alias} 계정]" + (f" (저장됨: {saved} — 그대로 두려면 아이디 칸에서 엔터)" if saved else ""))
    while True:
        user_id = input("  아이디만 입력: ").strip()
        if not user_id and saved:
            print("  건너뜀")
            break
        if " " in user_id:
            print("  공백이 있습니다. 아이디만 입력하세요 (비밀번호는 다음 줄에서 따로 묻습니다)")
            continue
        pw = getpass.getpass("  비밀번호 (입력해도 안 보임): ")
        try:
            Ebiz(user_id, pw).login().logout()
        except Exception as ex:
            print(f"  로그인 실패 — 저장 안 함. 다시 입력하세요.\n  {ex}")
            continue
        keyring.set_password(KEYRING_SERVICE, user_id, pw)
        save_account(alias, user_id)
        print(f"  {alias} 로그인 성공 — 저장 완료")
        break

print("\n끝. 이 창은 닫아도 됩니다.")
