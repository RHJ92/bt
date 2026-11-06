"""VS Code 세션 → 슬랙 담당 위임 도구 (2026-11-06, 🧭 총괄 세션 작성)

목적: 사용자가 한 업무를 하려고 VS Code 세션과 슬랙 채널을 오가지 않게 한다.
      VS Code 세션이 사용자 대신 슬랙 담당에게 일을 맡기고, 결과를 받아 그 세션에서 이어서 처리한다.

방식: 봇의 「예약 작업」 대기열(state/schedule.json)에 지금 시각으로 작업을 넣는다 → 봇이 최대 5분 안에
      그 담당 채널에 글을 올리고 담당을 실행한다(슬랙에도 기록이 남음) → 이 스크립트가 bot.log 로 시작·끝을
      확인하고 state/out/ 결과를 그대로 출력한다. 봇 코드는 고치지 않는다.

사용:
  python -X utf8 agents/shared/slack_bot/ask.py 재고통합담당 "할 일" --from "[소싱]"     # 맡기고 끝날 때까지 기다림
  python -X utf8 agents/shared/slack_bot/ask.py 재고통합담당 "할 일" --no-wait            # 맡기기만
  python -X utf8 agents/shared/slack_bot/ask.py --result <요청ID>                         # 나중에 결과 받기
  python -X utf8 agents/shared/slack_bot/ask.py --list                                    # 담당 이름 목록

주의
- 봇은 월~금 07~21시에만 대기열을 본다. 그 밖에 넣으면 다음 업무 시간에 시작한다.
- 담당은 1회 작업으로 돈다(세션 기록 없음). 이어서 물을 게 있으면 새로 맡기면서 앞 결과를 지시에 붙인다.
- 돈 나가는 일·외부 발송은 담당이 슬랙 승인 카드를 띄운다 — 승인은 사람이 누른다(안전장치, 예외).
"""
import argparse
import datetime as dt
import json
import re
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEDULE = HERE / "state" / "schedule.json"
AGENTS = HERE / "agents.json"
LOG = HERE / "logs" / "bot.log"
OUT = HERE / "state" / "out"
REQS = HERE / "state" / "ask_requests.json"


def load(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except ValueError:
        return default


def save(p, data):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def agent_names():
    d = load(AGENTS, {})
    return [k for k, v in d.items() if isinstance(v, dict) and v.get("지시", True) and not k.startswith("_")]


def in_window(now):
    return now.weekday() < 5 and 7 <= now.hour < 21


def submit(agent, task, origin):
    rid = uuid.uuid4().hex[:6]
    tag = f"[요청 {rid}]"
    text = (f"{tag} {origin} 세션이 호정님 대신 맡긴 일 — 결과는 이 스레드와 그 세션에 함께 전달됨. "
            f"승인이 필요한 건 승인 카드로 올려라.\n{task}")
    at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    job = {"at": at, "agent": agent, "task": text, "ask_id": rid}
    for _ in range(5):  # 봇과 동시에 쓰는 경우 대비 — 넣은 뒤 다시 읽어 확인
        jobs = load(SCHEDULE, [])
        jobs.append(job)
        save(SCHEDULE, jobs)
        time.sleep(1)
        if any(j.get("ask_id") == rid for j in load(SCHEDULE, [])):
            break
    else:
        sys.exit("대기열에 넣지 못했습니다 — 잠시 뒤 다시 실행하세요")
    reqs = load(REQS, {})
    reqs[rid] = {"agent": agent, "at": at, "from": origin, "task": task[:300]}
    save(REQS, reqs)
    return rid, at


def find_session(agent, rid):
    if not LOG.exists():
        return None, False
    session, done = None, False
    for line in LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"시작 \[" + re.escape(agent) + r"\] (\S+) .*\[요청 " + rid + r"\]", line)
        if m:
            session = m.group(1)
        if session and re.search(r"끝 \[" + re.escape(agent) + r"\] " + re.escape(session) + r" ", line):
            done = True
    return session, done


def result_of(session):
    files = sorted(OUT.glob(f"{session}_*.json"), key=lambda p: p.stat().st_mtime)
    if not files:
        return None
    r = load(files[-1], {}).get("result") or "(응답 없음)"
    extra = []
    if re.search(r"^\s*`*\s*HANDOFF\s+\{", r, re.M):
        extra.append("※ 담당이 다른 담당에게 일부를 넘겼습니다 — 그 회신은 슬랙 스레드에 붙습니다. 필요하면 --result 로 다시 확인하지 말고 새로 맡기세요")
    if re.search(r"^\s*`*\s*APPROVAL\s+\{", r, re.M):
        extra.append("※ 승인 카드가 슬랙에 올라갔습니다 — 승인은 호정님이 슬랙에서 누릅니다")
    r = re.sub(r"^\s*`*\s*(HANDOFF|APPROVAL)\s+\{.*$", "", r, flags=re.M).strip()
    return r + ("\n\n" + "\n".join(extra) if extra else "")


def wait(rid, agent, minutes):
    deadline = time.time() + minutes * 60
    started = False
    while time.time() < deadline:
        session, done = find_session(agent, rid)
        if session and not started:
            print(f"… {agent} 시작({session[:8]})", flush=True)
            started = True
        if done:
            res = result_of(session)
            if res:
                return res
        time.sleep(20)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent", nargs="?")
    ap.add_argument("task", nargs="?")
    ap.add_argument("--from", dest="origin", default="VS Code")
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--minutes", type=int, default=45)
    ap.add_argument("--result")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        print("\n".join(agent_names()))
        return
    if a.result:
        req = load(REQS, {}).get(a.result)
        if not req:
            sys.exit(f"요청 {a.result} 기록 없음")
        session, done = find_session(req["agent"], a.result)
        if not session:
            print(f"아직 시작 전 — {req['agent']} / 넣은 시각 {req['at']} (봇은 월~금 07~21시, 5분 간격)")
        elif not done:
            print(f"진행 중 — {req['agent']} ({session[:8]})")
        else:
            print(result_of(session) or "결과 파일 없음")
        return
    if not a.agent or not a.task:
        ap.error("담당 이름과 할 일을 주세요 (--list 로 담당 목록)")
    if a.agent not in agent_names():
        sys.exit(f"없는 담당: {a.agent}\n가능: {', '.join(agent_names())}")

    rid, at = submit(a.agent, a.task, a.origin)
    now = dt.datetime.now()
    print(f"맡김 — 요청 {rid} → {a.agent} ({at}). 슬랙 채널에도 글이 올라갑니다.")
    if not in_window(now):
        print("※ 지금은 봇 업무 시간(월~금 07~21시) 밖이라 다음 업무 시간에 시작합니다. 나중에: ask.py --result " + rid)
        return
    if a.no_wait:
        print(f"결과 받기: python -X utf8 agents/shared/slack_bot/ask.py --result {rid}")
        return
    res = wait(rid, a.agent, a.minutes)
    if res is None:
        print(f"{a.minutes}분 안에 안 끝났습니다. 나중에: python -X utf8 agents/shared/slack_bot/ask.py --result {rid}")
    else:
        print("=" * 20 + f" {a.agent} 결과 " + "=" * 20)
        print(res)


if __name__ == "__main__":
    main()
