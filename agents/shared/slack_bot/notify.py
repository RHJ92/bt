# 슬랙 알림 공용 함수 — 업무 스크립트·Claude 세션 훅·봇이 가져다 쓴다
# 토큰: Windows 자격 증명 관리자 "slack-bot" (set_slack_token.py 로 저장)
# 채널 구조 (2026-11-02: #총괄비서·#할일-확인필요 삭제): 모든 알림은 업무 채널로만. 예전: 정상 기록은 업무 채널, 사람이 손댈 것(warn·fail)은 업무 채널 + #할일-확인필요
# 토큰이 없거나 전송 실패해도 예외를 던지지 않는다 — 알림 실패가 본 작업을 멈추면 안 됨
#
# 명령줄: python notify.py <채널키> "<메시지>" [ok|warn|fail]    예) python notify.py order "✅ 완료"

import json
import sys
from pathlib import Path

import keyring
import requests

KEYRING_SERVICE, KEYRING_USER = "slack-bot", "업무비서"
_HERE = Path(__file__).resolve().parent


def _channels():
    """채널 키 → 채널 ID (agents.json 의 key + setup_channels.py 가 저장한 ID). 없으면 #이름"""
    agents = json.loads((_HERE / "agents.json").read_text(encoding="utf-8"))
    cfg_path = _HERE.parent / "config" / "slack.json"
    ids = json.loads(cfg_path.read_text(encoding="utf-8")).get("channels", {}) if cfg_path.exists() else {}
    out = {a["key"]: ids.get(name, "#" + name) for name, a in agents.items() if not name.startswith("_")}
    out["auto"] = out["todo"] = out["claude"]  # 옛 키 호환 — 전용 채널이 없어져 공통_작업완료로
    return out


CHANNELS = _channels()


def send(channel_key, text, level="ok"):
    """업무 채널로 보냄 (warn/fail 구분은 문구로만)"""
    token = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    if not token:
        return False
    targets = [CHANNELS.get(channel_key, channel_key)]
    ok = True
    for ch in targets:
        try:
            r = requests.post("https://slack.com/api/chat.postMessage", timeout=15,
                              headers={"Authorization": "Bearer " + token}, json={"channel": ch, "text": text})
            ok = ok and r.json().get("ok", False)
        except requests.RequestException:
            ok = False
    return ok


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("사용법: python notify.py <채널키> \"메시지\" [ok|warn|fail]")
    ok = send(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "ok")
    print("보냄" if ok else "못 보냄 (토큰 없음·채널 없음·봇 미초대)")
