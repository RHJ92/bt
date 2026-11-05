# agents.json 의 담당 채널을 슬랙에 맞춰 둔다 — 이전이름 채널은 이름 변경, 없는 채널은 생성, 주인 초대, 채널 설명 설정
# 실행: python -X utf8 setup_channels.py   (여러 번 실행해도 안전 — 이미 맞으면 건너뜀)
# 결과 채널 ID는 config/slack.json 의 "channels" 에 저장 → 봇이 ID로 듣는다(이름이 바뀌어도 동작)

import json
from pathlib import Path

import keyring
import requests

HERE = Path(__file__).resolve().parent
AGENTS = json.loads((HERE / "agents.json").read_text(encoding="utf-8"))
CONFIG = HERE.parent / "config" / "slack.json"
TOKEN = keyring.get_password("slack-bot", "업무비서")


def api(method, **data):
    r = requests.post(f"https://slack.com/api/{method}", headers={"Authorization": "Bearer " + TOKEN},
                      data=data, timeout=20).json()
    return r


def all_channels():
    out, cursor = {}, None
    while True:
        r = api("conversations.list", types="public_channel", limit=200, exclude_archived="true",
                **({"cursor": cursor} if cursor else {}))
        for c in r.get("channels", []):
            out[c["name"]] = c
        cursor = r.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            return out


cfg = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
owner = cfg.get("owner")
chans = all_channels()
ids = {}
for name, a in AGENTS.items():
    if name.startswith("_"):
        continue
    c = chans.get(a.get("채널명", name)) or chans.get(name)
    if not c and a.get("이전이름") in chans:
        old = chans[a["이전이름"]]
        api("conversations.join", channel=old["id"])
        r = api("conversations.rename", channel=old["id"], name=a.get("채널명", name))
        print(f"이름 변경 #{a['이전이름']} → #{name}: {'성공' if r.get('ok') else r.get('error')}")
        c = r.get("channel") if r.get("ok") else old
    if not c:
        r = api("conversations.create", name=a.get("채널명", name))
        print(f"생성 #{name}: {'성공' if r.get('ok') else r.get('error')}")
        c = r.get("channel")
    if not c:
        continue
    ids[name] = c["id"]
    api("conversations.join", channel=c["id"])
    if owner:
        api("conversations.invite", channel=c["id"], users=owner)
    api("conversations.setPurpose", channel=c["id"], purpose=a["역할"])

cfg["channels"] = ids
CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n채널 ID 저장:", ", ".join(f"#{k}" for k in ids))
