"""작업중 표시판 — 슬랙 담당과 VS Code 세션이 같은 거점 일을 동시에 하지 않게 (2026-11-04 사용자 요청)

거점 = 저장소 기준 폴더 (예: settlements/리우, inventory_management). 한쪽이 다른 쪽의 상위·하위 폴더여도 겹친 것으로 본다.
표시는 2시간이 지나면 무시한다 (작업이 중간에 죽어 지우지 못한 경우).

  python agents/shared/slack_bot/work_board.py list
  python agents/shared/slack_bot/work_board.py check <거점> --who "VS Code"   → 다른 쪽 표시가 있으면 출력하고 종료코드 1
  python agents/shared/slack_bot/work_board.py add <거점> "<할 일>" --who "VS Code"   → id 출력
  python agents/shared/slack_bot/work_board.py done <id>
"""
import argparse
import datetime as dt
import json
import sys
import uuid
from pathlib import Path

BOARD = Path(__file__).resolve().parent / "state" / "작업중.json"
STALE_H = 2


def _load():
    try:
        items = json.loads(BOARD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    cut = dt.datetime.now() - dt.timedelta(hours=STALE_H)
    return [x for x in items if dt.datetime.fromisoformat(x["시작"]) > cut]


def _save(items):
    BOARD.parent.mkdir(parents=True, exist_ok=True)
    BOARD.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def _norm(folder):
    return folder.replace("\\", "/").strip("/")


def _overlap(a, b):
    a, b = _norm(a), _norm(b)
    return bool(a and b) and (a == b or a.startswith(b + "/") or b.startswith(a + "/"))


def _kind(who):
    return "슬랙" if who.startswith("슬랙") else "VS Code"


def add(folder, task, who):
    items = _load()
    wid = uuid.uuid4().hex[:8]
    items.append({"id": wid, "거점": _norm(folder), "누가": who, "할일": task[:80],
                  "시작": dt.datetime.now().isoformat(timespec="minutes")})
    _save(items)
    return wid


def done(wid):
    _save([x for x in _load() if x["id"] != wid])


def clear(prefix):
    """봇 시작 때 지난 슬랙 표시 정리"""
    _save([x for x in _load() if not x["누가"].startswith(prefix)])


def check(folder, who):
    """같은 거점에서 다른 쪽(슬랙 ↔ VS Code)이 하고 있는 일"""
    return [x for x in _load() if _overlap(folder, x["거점"]) and _kind(x["누가"]) != _kind(who)]


def text(x):
    return f"{x['누가']} · {x['거점']} · {x['할일']} (시작 {x['시작'][5:].replace('T', ' ')})"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["list", "check", "add", "done"])
    p.add_argument("args", nargs="*")
    p.add_argument("--who", default="VS Code")
    a = p.parse_args()
    if a.cmd == "list":
        print("\n".join(text(x) for x in _load()) or "작업 중 표시 없음")
    elif a.cmd == "check":
        hits = check(a.args[0], a.who)
        print("\n".join(text(x) for x in hits) or "겹치는 작업 없음")
        sys.exit(1 if hits else 0)
    elif a.cmd == "add":
        print(add(a.args[0], a.args[1], a.who))
    else:
        done(a.args[0])
