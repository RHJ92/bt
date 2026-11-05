# 슬랙 봇 토큰(xoxb-…) 저장 + 시험 메시지 전송
# 실행: python "C:\Users\BLUETREND\류호정\bt\agents\shared\slack_bot\set_slack_token.py"
# 토큰은 붙여넣어도 화면에 안 보이는 게 정상. 채팅창에는 절대 붙이지 말 것

import getpass
import sys

import keyring
import requests

from notify import CHANNELS, KEYRING_SERVICE, KEYRING_USER, send

token = getpass.getpass("Bot User OAuth Token (xoxb-로 시작, 붙여넣기 후 엔터): ").strip()
if not token.startswith("xoxb-"):
    sys.exit("xoxb- 로 시작하는 토큰이 아닙니다 — 저장 안 함")
r = requests.post("https://slack.com/api/auth.test", headers={"Authorization": "Bearer " + token}, timeout=15).json()
if not r.get("ok"):
    sys.exit(f"토큰 확인 실패 — 저장 안 함 ({r.get('error')})")
keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)
print(f"저장 완료 — 워크스페이스 {r.get('team')}, 봇 {r.get('user')}")

for key, ch in CHANNELS.items():
    ok = send(key, f"👋 {ch} 연결 시험 — 이 메시지가 보이면 성공")
    print(f"  {ch}: {'보냄' if ok else '실패 — 채널을 만들고 /invite @업무비서 했는지 확인'}")
