# 이카운트 IMAP 로그인 실패 진단 — 아이디 형식·인증 방식을 바꿔 가며 시험 (저장 안 함)
# 실행: python "C:\Users\BLUETREND\류호정\bt\agents\shared\mail_intake\diagnose_login.py"
# 비밀번호는 화면에 안 보이고, 어디에도 저장하지 않는다. 결과(성공/실패 문구)만 출력

import getpass
import imaplib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecount_imap import HOST, PORT, USER

pw = getpass.getpass(f"{USER} 웹메일 비밀번호: ")
print(f"(입력 길이 {len(pw)}자, 앞뒤 공백 {'있음' if pw != pw.strip() else '없음'})\n")

ids = [USER, USER.split("@")[0]]
for uid in ids:
    for method in ("LOGIN", "AUTHENTICATE PLAIN"):
        imap = imaplib.IMAP4_SSL(HOST, PORT)
        try:
            if method == "LOGIN":
                imap.login(uid, pw)
            else:
                imap.authenticate("PLAIN", lambda _: f"\0{uid}\0{pw}".encode())
            print(f"  성공  {uid:<28} {method}")
            imap.logout()
        except Exception as e:
            print(f"  실패  {uid:<28} {method}  → {e}")
