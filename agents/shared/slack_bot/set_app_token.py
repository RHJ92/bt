# 슬랙 App-Level Token(xapp-…, Socket Mode용) 저장 + 연결 시험
# 실행: python "C:\Users\BLUETREND\류호정\bt\agents\shared\slack_bot\set_app_token.py"
# 토큰은 붙여넣어도 화면에 안 보이는 게 정상. 채팅창에는 붙이지 말 것

import getpass
import sys

import keyring
import requests

token = getpass.getpass("App-Level Token (xapp-로 시작, 붙여넣기 후 엔터): ").strip()
if not token.startswith("xapp-"):
    sys.exit("xapp- 로 시작하는 토큰이 아닙니다 — 저장 안 함")
r = requests.post("https://slack.com/api/apps.connections.open",
                  headers={"Authorization": "Bearer " + token}, timeout=15).json()
if not r.get("ok"):
    sys.exit(f"연결 시험 실패 — 저장 안 함 ({r.get('error')}). Socket Mode가 켜져 있는지, 토큰 범위가 connections:write 인지 확인")
keyring.set_password("slack-bot", "app-token", token)
print("저장 완료 — Socket Mode 연결 확인됨")
