# 이카운트 웹메일 계정 등록 — 비밀번호를 Windows 자격 증명 관리자에 저장 + 접속 시험 (읽기 전용)
# 실행: python "C:\Users\BLUETREND\류호정\bt\agents\shared\mail_intake\set_password.py"
# 한 줄에 하나씩: 계정 번호 → 메일 주소 → 서버 번호 → 비밀번호(화면에 안 보이는 게 정상)
# 먼저 그 계정 웹메일에서: 프로필 → 개인기능설정 → 외부연동설정 → [메일 클라이언트 사용] = 사용
# 저장 위치 확인·삭제: 제어판 → 자격 증명 관리자 → Windows 자격 증명 → "ecount-imap"

import getpass
import os
import sys

import keyring

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecount_imap import KEYRING_SERVICE, accounts, list_folders, login, open_readonly, save_account  # noqa: E402

CHOICES = ["발주서수신", "옥된장", "철산장", "석문어", "정백선", "개인"]  # 개인 = 구매팀 담당자 본인 메일 (단가 변경 요청 등 발송용)

while True:
    acc = accounts()
    print("\n계정:")
    for i, name in enumerate(CHOICES, 1):
        a = acc.get(name)
        print(f"  {i}) {name}" + (f"  — 등록됨 {a['user']}" if a and keyring.get_password(KEYRING_SERVICE, a["user"])
                                  else "  — 미등록"))
    sel = input("등록할 계정 번호 (끝내려면 엔터): ").strip()
    if not sel:
        break
    if not sel.isdigit() or not 1 <= int(sel) <= len(CHOICES):
        print("번호만 입력하세요")
        continue
    alias = CHOICES[int(sel) - 1]
    old = acc.get(alias, {})
    user = input(f"  {alias} 메일 주소{' (엔터 = ' + old['user'] + ')' if old else ''}: ").strip() or old.get("user", "")
    if "@" not in user or " " in user:
        print("  메일 주소 형식이 아닙니다 — 주소만 입력하세요 (비밀번호는 다음에 따로 묻습니다)")
        continue
    srv = input("  서버 번호 — 외부연동가이드 「받는서버설정」의 wmbox 뒤 숫자 (엔터 = 3): ").strip() or "3"
    host = f"wmbox{srv}.ecount.com"
    pw = getpass.getpass("  웹메일 비밀번호 (입력해도 안 보임): ")
    try:
        imap = login(user, host, pw)
    except Exception as e:
        print(f"  로그인 실패 — 저장 안 함. 메일 클라이언트 사용 설정·서버 번호·비밀번호를 확인하세요.\n  {e}")
        continue
    keyring.set_password(KEYRING_SERVICE, user, pw)
    save_account(alias, user, host)
    print(f"  {alias} 로그인 성공 — 저장 완료. 메일함:")
    for name, raw in list_folders(imap):
        try:
            print(f"    {name:<20} {open_readonly(imap, raw):>6}통")
        except Exception:
            pass
    imap.logout()

print("\n끝. 이 창은 닫아도 됩니다.")
