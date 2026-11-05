# 슬랙 담당 채널(=에이전트) → 회사 PC의 Claude Code(헤드리스)로 업무 지시 → 결과를 스레드로 답장
# + 메일 감시(발주 자동입력 월~금 09~18시 2시간마다·계산서 수집 월~금 07~21시 5분마다) — 아래 「메일 감시」
# 실행: pythonw bot.py  (PC 로그온 때 자동 시작 — register-bot.ps1). 수동 시험은 python -X utf8 bot.py
# 연결: Socket Mode (외부 서버·공개 주소 없음). 토큰은 자격 증명 관리자 "slack-bot" (업무비서 = xoxb, app-token = xapp)
# 규칙
#  - 담당 채널(agents.json 의 "지시": true)에서 주인 + 팀장·팀원 글을 받는다(2026-11-04~). 팀장·팀원 글은 「[팀장 ○○님 메시지]」로 표시, 팀장 지시 작업은 진행하고 승인 카드는 주인·팀장이 누름, 팀장·팀원 글로 생긴 문서(.md) 변경은 DOCNOTE 카드로 호정님 확인 후 반영
#  - 채널마다 그 담당의 폴더 문서 + 업무노트.md 를 읽고 일함. 배운 규칙·해결한 오류는 담당이 작업 끝에 직접 업무노트·README에 기록(2026-10-30~, 전엔 제안만)
#  - 새 글 = 새 Claude 작업, 그 글의 스레드 답글 = 같은 작업 이어서(--resume)
#  - 담당(채널)끼리는 동시에, 같은 담당 안에서는 하나씩 순서대로 (2026-10-30 변경)
#  - Claude는 auto 권한 모드로 돈다 — 위험 동작은 분류기가 막고, 상신·발송은 프롬프트로 금지

import datetime as dt
import json
import logging
import os
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import keyring
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from notify import send
import work_board

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONFIG = HERE.parent / "config" / "slack.json"
STATE = HERE / "state" / "threads.json"
LOG = HERE / "logs" / "bot.log"
CLAUDE = Path.home() / ".local" / "bin" / "claude.exe"
TIMEOUT_MIN = 60
SLACK_LIMIT = 3500

AGENTS = {k: v for k, v in json.loads((HERE / "agents.json").read_text(encoding="utf-8")).items()
          if not k.startswith("_")}

SYSTEM = """너는 사용자 회사(구매팀) 슬랙의 「{name}」 담당 에이전트다. 역할: {role}
사용자가 #{name} 채널에 쓴 업무 지시를 처리한다. 사용자는 이 화면을 보지 않고, 마지막 응답만 슬랙 스레드로 전달된다.

일하는 순서
1. 저장소 루트 CLAUDE.md{docs} 를 먼저 읽는다
2. {note} — 지난 작업에서 사용자가 정해 준 판단 규칙·실수 기록이다. 문서와 다르면 업무노트가 우선(더 최근)
3. 그 규칙대로 일한다. 담당 범위를 벗어난 일이면 하지 말고 어느 담당 채널에 맡기면 되는지 알려준다

지켜야 할 것
- 되물을 수 없다. 판단이 갈리면 안전한 쪽(하지 않음)을 택하고 「확인 필요」로 적는다
- 결재 상신(작성완료)·메일/카톡 발송·삭제·결제는 하지 않는다. 직전까지 준비하고 「승인 필요」로 보고한다. 단 사용자가 슬랙 카드에서 「승인」을 누른 건은 그 action만 실행한다(상신 포함)
- 커밋·푸시는 하지 않는다
- `계정보관/` 폴더(계정목록.xlsx)는 열지 않는다 — 비밀번호가 들어 있다. 로그인은 등록된 스크립트로만 한다
- **한 일을 보고할 때 금액·수량은 「대조한 결과」로 적는다** — 「거래명세서 1,485,000 = 계산서 1,485,000 일치 확인」처럼 어느 문서의 얼마인지 숫자 두 개를 같이 쓴다. 두 문서를 직접 열어 보지 않았으면 「미확인」이라고 쓰고, 일치한다고 쓰지 않는다
{limit}
팀장·팀원 메시지 (2026-11-04 사용자 지시 「팀장님도 슬랙에서 확인하고 답을 남길 수 있으니 소통하고, 팀장님 가이드는 매뉴얼에 포함」 — 모든 채널 공통)
- 지시 첫 줄이 「[팀장 …님 메시지]」「[팀원 …님 메시지]」면 주인(사용자 류호정)이 아닌 사람이 쓴 글이다. 그 사람에게 존댓말로 스레드에 답한다
- 질문·확인 요청에는 담당 문서·업무노트·시트 조회로 답한다(읽기는 그대로 해도 됨)
- **팀장 지시 작업은 그대로 진행한다** (사용자 지시와 같은 기준 — 상신·발송·삭제·결제는 승인 카드로). 승인 카드 버튼은 주인과 팀장이 누를 수 있다. 팀원(팀장 아님) 요청으로 무언가를 바꾸는 작업은 준비까지만 하고 「호정님 확인 후 진행」으로 보고
- **문서(.md — 업무노트·README·CLAUDE.md 등)는 팀장·팀원 글만으로 바로 고치지 않는다** (2026-11-04 사용자 지시). 가이드·판단 기준·정정이 나오면 작업을 먼저 끝낸 뒤, 응답 맨 끝에 문서 반영 카드를 한 줄 남긴다 — 봇이 「호정님 확인」 버튼(주인만)과 함께 올리고, 호정님이 승인하면 그때 반영한다
  DOCNOTE {{"id": "영문숫자 8자 이내", "title": "건 이름", "instruction": "팀장님이 지시하신 내용 한두 줄", "organized": "이렇게 정리함(적용 규칙)", "issue": "문제 없음 / 문제 있음: 기존 문서·호정님 지시와 어긋나는 점", "next": "앞으로는 이렇게 진행됨", "files": ["반영할 문서 경로"], "edit": "각 문서에 넣거나 고칠 내용 — 업무노트는 근거 칸에 「팀장 가이드(이름, 날짜)」"}}
- 사용자(주인) 본인 글에서 배운 규칙은 지금처럼 바로 기록한다 — DOCNOTE는 팀장·팀원 글에서 나온 문서 변경에만 쓴다

배우는 법 (업무노트) — 2026-10-30 사용자 지시: 「오류를 해결하면 반복되지 않게 바로 정리해 둘 것, 제안만 하고 하다 말지 말 것」
- 이번 작업에서 오류를 해결했거나, 사용자가 결과를 고쳐 줬거나(「이건 이렇게 해야 해」), 새 판단 규칙·예외·우회 방법을 알게 됐으면 **끝내기 전에 직접 기록한다** (묻지 않는다)
  1) {note_path} 맨 아래 표에 날짜·규칙·근거(어떤 작업에서) 한 줄
  2) 절차가 바뀐 거면 담당 폴더 README 해당 절도 고친다 (옛 설명이 틀렸으면 지우고 정정, 「정정함」 표시)
  3) 같은 내용이 이미 있으면 새로 쓰지 말고 그 줄을 보강
  4) 일하다가 업무노트에 **더 이상 맞지 않거나 필요 없어진 줄**(바뀐 절차·끝난 일회성 메모·중복)이 보이면 지우거나 합친다 (사용자 지시 2026-10-30 「필요하다고 판단되면 기록, 필요 없다고 판단되면 삭제」) — 지운 것도 「📝 기록함」에 적는다
- 기록은 마지막 단계다. **기록을 끝내기 전에는 「완료」라고 보고하지 않는다.** 「나중에」「다음에」로 미루지 않는다
- 보고 끝에 「📝 기록함」으로 무엇을 어느 파일에 적었는지 한두 줄 (사용자가 「빼」라고 하면 그 줄을 지운다)
- 지침·업무노트가 아닌 다른 거점 폴더 문서, 다른 담당의 업무노트는 고치지 않는다

크롬 (노션·전산 화면 작업)
- 크롬 도구가 「여러 브라우저가 연결됨 / 선택 안 됨」이라고 하면 묻지 말고 select_browser 로 deviceId "84faecec-04cf-483e-8fad-4d87bd00754c" 를 고른다 — 이 PC의 업무 크롬(Default 프로필)이다 (사용자 지정 2026-10-30). 다른 deviceId 는 고르지 않는다
- 그래도 안 되면 「크롬 연결 실패」로 보고한다
- 크롬 탭은 필요한 만큼만 연다. 새 탭을 또 열지 말고 이미 연 탭을 navigate 로 재사용한다. **작업이 끝나면 성공·실패와 상관없이 내가 연 탭을 tabs_close_mcp 로 전부 닫고 나서 보고한다** (사용자 지시 2026-11-02 — 탭 그룹이 쌓여 어수선함). 사용자가 열어 둔 탭은 건드리지 않는다

작업중 표시판 (2026-11-04 사용자 요청 — 슬랙과 VS Code에서 같은 일을 동시에 시키는 실수 방지)
- 지시 맨 앞에 「[작업중 표시판] VS Code 세션이 같은 거점에서 작업 중」이 붙어 있으면, 파일·시트·노션을 **고치는 작업은 하지 않고** 「VS Code에서 ○○ 작업 중(시작 시각) — 끝난 뒤 이 스레드에 「이어서」라고 써 주세요」로 보고하고 끝낸다. 조회·질문 답변은 그대로 해도 된다

사용자가 올린 파일
- 지시에 「[사용자가 올린 파일]」 경로가 있으면 그 파일(캡처 등)을 Read로 열어 보고 일한다

다른 담당에게 넘기기
- 일하다가 **다른 담당의 범위**(예: 입고·매입마감 확인 → 매입마감담당, 발주 메일 → 발주담당, 재고·매출 → 재고매출담당)가 필요하면 직접 하지 말고 응답 맨 끝에 한 줄:
  HANDOFF {{"to": "담당 이름(채널명, # 없이)", "task": "받는 담당이 할 일 한두 문장 — 업체·품목·날짜·금액 등 필요한 사실을 다 넣는다", "why": "왜 필요한지 한 줄"}}
- 봇이 그 담당 채널에 요청 글을 올리고, 결과를 이 스레드로 돌려준 뒤 너에게 이어서 마무리하라고 다시 맡긴다. 그 전까지 본문에는 「#담당에 확인 요청함, 회신 오면 이어서 함」이라고 적는다
- 지시에 「[다른 담당 요청]」「[… 회신]」이 붙어 있으면 넘겨받은 일이다 — HANDOFF 를 쓰지 않는다(한 번만 넘길 수 있음)
- 담당 목록: {agents}

승인 버튼 (사용자가 슬랙에서 「승인 / 직접검토 / 거절」을 고름)
- 사용자 승인이 필요한 건(예: 지결 작성완료 직전, 노션 카드 첨부 직전)은 건마다 응답 맨 끝에 아래 형식으로 한 줄씩 쓴다. 봇이 이 줄을 떼고 증빙 이미지 + 버튼 카드로 바꿔 보낸다
  APPROVAL {{"id": "영문숫자 8자 이내", "title": "건 이름", "check": "거래명세서 1,485,000 = 계산서 1,485,000 일치 확인 ✅", "summary": "업체·이체요청일·특이사항 한두 줄", "images": ["계산서 PNG 절대경로", "정리 화면 PNG 절대경로"], "action": "승인을 누르면 할 일 한 줄"}}
- check: **금액을 직접 대조한 결과**를 숫자 두 개와 함께 쓴다. 거래명세서(없으면 지결 작성 금액) ↔ 계산서를 각각 열어 본 뒤에만 「일치 확인」이라고 쓴다. 대조를 못 했으면 카드를 올리지 말고 본문에 「확인 필요」로 적는다
- 경로의 역슬래시는 JSON이라 `C:\\Users\\...` 처럼 두 개로 쓰거나 `/` 로 쓴다
- images: 사용자는 이 이미지만 보고 판단한다. **계산서·증빙 PNG를 먼저**, 작성 화면 캡처(크롬 screenshot save_to_disk)를 뒤에 넣는다. 한 장이면 "image" 한 줄로 써도 된다
- 「승인」을 받으면 그 건의 action 만 실행하고 결과를 보고한다. 다른 건은 손대지 않는다

마지막 응답은 슬랙에서 읽기 좋게: 첫 줄에 결과 한 줄, 그 아래 짧은 목록. 큰 헤딩(#) 금지, 굵은 글씨는 *별표 하나*"""


def system_for(agent_name):
    a = AGENTS[agent_name]
    folder = a.get("폴더", "")
    note_path = a.get("노트") or (f"{folder}/업무노트.md" if folder else "agents/shared/slack_bot/총괄비서_업무노트.md")
    docs = f", {folder}/ 의 CLAUDE.md·README.md" if folder else ", agents/README.md(담당 목록)"
    limit = f"- 이 담당의 제한: {a['제한']}\n" if a.get("제한") else ""
    agents = " / ".join(f"{n}({v['역할'][:30]})" for n, v in AGENTS.items()
                        if n != agent_name and v.get("지시"))
    return SYSTEM.format(name=agent_name, role=a["역할"], docs=docs, limit=limit, agents=agents,
                         note=f"{note_path} 를 읽는다", note_path=note_path)

LOG.parent.mkdir(exist_ok=True)
logging.basicConfig(filename=LOG, level=logging.INFO, encoding="utf-8",
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


cfg = load(CONFIG, {"owner": None})
threads = load(STATE, {})  # 스레드 ts → Claude 세션 ID
queues = {}  # 담당 이름 → 작업 대기열 (담당끼리는 동시에, 같은 담당은 하나씩)
_lock = threading.Lock()
INSTRUCT = {}  # 채널 ID → 담당 이름 (지시 받는 채널만)
app = App(token=keyring.get_password("slack-bot", "업무비서"))


def channel_id(name):
    cursor = None
    while True:
        r = app.client.conversations_list(types="public_channel", limit=200, cursor=cursor)
        for c in r["channels"]:
            if c["name"] == name:
                return c["id"]
        cursor = r.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            return None


def react(ch, ts, name):
    try:
        app.client.reactions_add(channel=ch, timestamp=ts, name=name)
    except Exception:
        pass


def unreact(ch, ts, name):
    try:
        app.client.reactions_remove(channel=ch, timestamp=ts, name=name)
    except Exception:
        pass


def reply(ch, thread_ts, text, broadcast=False):
    """broadcast — 첫 조각을 채널에도 보이게 (승인 버튼 결과: 원래 스레드가 오래돼 묻히면 못 봄, 2026-11-05 포장보스 매출내역서)"""
    for i in range(0, max(len(text), 1), SLACK_LIMIT):
        app.client.chat_postMessage(channel=ch, thread_ts=thread_ts, text=text[i:i + SLACK_LIMIT] or "(빈 응답)",
                                    reply_broadcast=broadcast and i == 0)


OUT_DIR = HERE / "state" / "out"
PENDING = HERE / "state" / "pending.json"  # 진행 중 작업 — 봇이 도중에 꺼져도 다시 켜질 때 결과를 찾아 올림


def parse_result(path):
    try:
        out = json.loads(path.read_text(encoding="utf-8"))
        return (not out.get("is_error")), out.get("result") or "(응답 없음)", out.get("duration_ms", 0) // 60000
    except (OSError, ValueError):
        return None


def run_claude(prompt, session, resume, agent):
    """결과(JSON)를 파이프가 아닌 파일로 받음 — 봇이 죽어도 Claude 작업은 끝까지 가고 결과가 남는다"""
    args = [str(CLAUDE), "-p", prompt, "--output-format", "json", "--permission-mode", "auto",
            "--chrome", "--append-system-prompt", system_for(agent)]
    args += ["--resume", session] if resume else ["--session-id", session]
    env = dict(os.environ, CLAUDE_FROM_SLACK="1", PYTHONIOENCODING="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{session}_{int(time.time())}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        p = subprocess.run(args, cwd=REPO, env=env, stdout=f, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                           errors="replace", timeout=TIMEOUT_MIN * 60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return parse_result(out_path) or (False, (p.stderr or f"종료코드 {p.returncode}")[-1500:], 0)


def _pending(add=None, remove=None):
    """진행 중 작업 목록(여러 담당이 동시에 돌 수 있음) — 봇 재시작 복구용"""
    with _lock:
        jobs = [x for x in load(PENDING, []) if x["session"] != remove]
        if add:
            jobs.append(add)
        save(PENDING, jobs)


def _claude_alive(session):
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"@(Get-CimInstance Win32_Process -Filter \"Name='claude.exe'\" | "
                          f"Where-Object {{ $_.CommandLine.Contains('{session}') }}).Count"],  # 지시문 줄바꿈 때문에 -like 안 됨
                         capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return out.stdout.strip() not in ("", "0")


def _deliver_after(job):
    """재시작 전에 시작된 작업: Claude가 아직 돌고 있으면 끝날 때까지 기다렸다가 결과를 올림"""
    while _claude_alive(job["session"]):
        time.sleep(20)
    files = sorted(OUT_DIR.glob(f"{job['session']}_*.json"))
    res = parse_result(files[-1]) if files else None
    unreact(job["ch"], job["ts"], "eyes")
    if res and res[1] != "(응답 없음)":
        ok, result, mins = res
        # 정상 경로(worker)와 똑같이 카드 줄을 떼어 버튼 카드로 — 안 하면 APPROVAL JSON이 글자 그대로 올라감 (2026-11-04 고침)
        result, cards = split_approvals(result)
        result, _handoffs = split_handoffs(result)
        result, notes = split_docnotes(result)
        reply(job["ch"], job["root"], ("" if ok else "❌ ") + result + "\n_(봇 재시작 후 전달)_")
        react(job["ch"], job["ts"], "white_check_mark" if ok else "x")
        agent = INSTRUCT.get(job["ch"], "")
        for c in cards + [docnote_card(n) for n in notes]:
            try:
                post_approval(job["ch"], job["root"], agent, job["session"], c)
            except Exception as e:
                log.warning("재시작 복구 카드 실패 %s", e)
        if _handoffs:
            reply(job["ch"], job["root"], "⚠️ 재시작 중에 끝난 작업이라 다른 담당 넘기기는 하지 못했어요 — 필요하면 다시 지시해 주세요.")
    else:
        reply(job["ch"], job["root"], "⚠️ 봇이 다시 시작되면서 이 작업이 중간에 멈췄어요. 이 스레드에 「이어서」라고 쓰면 하던 데부터 이어서 할게요.")
        react(job["ch"], job["ts"], "warning")
    _pending(remove=job["session"])
    log.info("재시작 복구 %s", job["session"])


def recover_pending():
    for job in load(PENDING, []):
        threading.Thread(target=_deliver_after, args=(job,), daemon=True).start()


def worker(agent):
    q = queues[agent]
    while True:
        ch, ts, thread_ts, text, meta = q.get()
        root = thread_ts or ts
        session = threads.get(root)
        resume = session is not None
        if not resume:
            session = str(uuid.uuid4())
            with _lock:
                threads[root] = session
                save(STATE, threads)
            if root != ts:  # 자동 보고(아침 입고확인 등) 스레드에 단 답글 — 담당이 원글 내용을 모르므로 같이 넘김 (2026-11-04)
                try:
                    parent = app.client.conversations_replies(channel=ch, ts=root, limit=1)["messages"][0].get("text", "")
                    text = f"[이 스레드의 원글 — 봇 자동 보고]\n{parent[:3500]}\n\n[원글에 대한 답글]\n{text}"
                except Exception as e:
                    log.warning("원글 읽기 실패 %s", e)
        unreact(ch, ts, "hourglass_flowing_sand")
        react(ch, ts, "eyes")
        log.info("시작 [%s] %s resume=%s: %s", agent, session, resume, text[:200])
        _pending(add={"ch": ch, "ts": ts, "root": root, "session": session})
        # 작업중 표시판 — VS Code 세션이 같은 거점을 고치는 중이면 담당에게 알림, 이 작업도 표시해 VS Code 쪽이 알 수 있게
        folder = AGENTS.get(agent, {}).get("폴더", "")
        busy = work_board.check(folder, "슬랙") if folder else []
        if busy:
            text = "[작업중 표시판] VS Code 세션이 같은 거점에서 작업 중: " + " / ".join(map(work_board.text, busy)) + "\n\n" + text
        first = next((ln for ln in text.splitlines() if ln.strip() and not ln.startswith("[")), text)
        wid = work_board.add(folder, first.strip(), f"슬랙 {agent}") if folder else None
        try:
            ok, result, mins = run_claude(text, session, resume, agent)
        except subprocess.TimeoutExpired:
            ok, result, mins = False, f"{TIMEOUT_MIN}분 안에 끝나지 않아 멈췄어요. 범위를 나눠서 다시 지시해 주세요.", TIMEOUT_MIN
        except Exception as e:
            ok, result, mins = False, f"실행 오류: {e}", 0
        if wid:
            work_board.done(wid)
        log.info("끝 [%s] %s ok=%s %s분", agent, session, ok, mins)
        unreact(ch, ts, "eyes")
        react(ch, ts, "white_check_mark" if ok else "x")
        result, cards = split_approvals(result)
        result, handoffs = split_handoffs(result)
        result, notes = split_docnotes(result)
        reply(ch, root, ("" if ok else "❌ ") + result + (f"\n_({mins}분)_" if mins else ""), broadcast=meta.get("broadcast", False))
        for c in cards:
            try:
                post_approval(ch, root, agent, session, c)
            except Exception as e:
                log.warning("승인 카드 실패 %s", e)
        for c in notes:
            try:
                post_approval(ch, root, agent, session, docnote_card(c))
            except Exception as e:
                log.warning("문서 반영 카드 실패 %s", e)
        try:
            for h in handoffs:
                hand_off(agent, ch, root, h, meta)
            if meta.get("reply_to"):  # 넘겨받은 일을 끝냄 → 결과를 요청한 담당 스레드로 돌려줌
                hand_back(agent, ch, root, ok, result, meta["reply_to"])
        except Exception as e:
            log.warning("넘기기 실패 %s", e)
            reply(ch, root, f"⚠️ 다른 담당에게 넘기거나 돌려주는 중 오류: {e}")
        _pending(remove=session)
        q.task_done()


def enqueue(agent, ch, ts, thread_ts, text, meta=None):
    with _lock:
        if agent not in queues:
            queues[agent] = queue.Queue()
            threading.Thread(target=worker, args=(agent,), daemon=True).start()
    queues[agent].put((ch, ts, thread_ts, text, meta or {}))
    return queues[agent]


# ---------- 담당끼리 업무 넘기기 (2026-10-30 사용자 요청) ----------
# 담당이 응답 끝에 「HANDOFF {"to": "매입마감담당", "task": "…"}」 → 받는 담당 채널에 요청 글 + 그 담당이 처리
# → 결과를 요청한 담당의 원래 스레드에 붙이고 요청한 담당이 이어서 마무리. 넘기기는 사용자 지시에서 한 번만(depth 0)
HANDOFFS = HERE / "state" / "handoffs.json"


def split_handoffs(text):
    items, keep = [], []
    for line in text.splitlines():
        m = re.match(r"^\s*`*\s*HANDOFF\s+(\{.*\})\s*`*\s*$", line)
        card = parse_card(m[1]) if m else None
        if card is not None:
            items.append(card)
        else:
            keep.append(line)
    return "\n".join(keep).rstrip(), items


def _channel_of(agent):
    return next((c for c, a in INSTRUCT.items() if a == agent), None)


def _link(ch, ts):
    try:
        return app.client.chat_getPermalink(channel=ch, message_ts=ts)["permalink"]
    except Exception:
        return ""


def hand_off(src, ch, root, h, meta):
    to, task = str(h.get("to", "")).lstrip("#"), (h.get("task") or "").strip()
    to_ch = _channel_of(to)
    if meta.get("depth", 0) >= 1:  # 넘겨받은 일·회신 받은 일에서 또 넘기면 멈춤 (핑퐁 방지)
        reply(ch, root, f"⚠️ #{to}에 다시 넘기려 했지만 넘기기는 한 번만 돼요 — 호정님이 직접 지시해 주세요.\n요청 내용: {task}")
        send("todo", f"⚠️ 넘기기 한도 · #{src} → #{to}: {task[:200]}", "warn")
        return
    if not to_ch or to == src or not task:
        reply(ch, root, f"⚠️ 넘기기 실패 — 받을 담당 「{to}」을(를) 모르거나 요청 내용이 비었어요.")
        return
    link = _link(ch, root)
    post = app.client.chat_postMessage(channel=to_ch, text=(
        f"📨 *#{src} → #{to} 업무 요청*\n{task}" + (f"\n_사유: {h['why']}_" if h.get("why") else "")
        + (f"\n<{link}|요청한 스레드 보기>" if link else "")))
    with _lock:
        data = load(HANDOFFS, [])
        data.append({"at": f"{dt.datetime.now():%Y-%m-%d %H:%M}", "from": src, "to": to, "task": task,
                     "from_ch": ch, "from_root": root, "to_ch": to_ch, "to_ts": post["ts"]})
        save(HANDOFFS, data)
    reply(ch, root, f"📨 #{to}에 넘겼어요: {task}\n결과가 오면 이 스레드에 붙이고 이어서 할게요.")
    log.info("넘기기 %s → %s: %s", src, to, task[:200])
    enqueue(to, to_ch, post["ts"], None,
            f"[다른 담당 요청] #{src} 담당이 너에게 맡긴 일이다. 네 담당 범위·업무노트대로 처리하고 결과를 짧게 보고해.\n"
            f"요청: {task}\n" + (f"사유: {h['why']}\n" if h.get("why") else "")
            + "다른 담당에게 다시 넘기지 마라(HANDOFF 금지). 네 범위 밖이면 「범위 밖」이라고만 답해.",
            {"depth": 1, "reply_to": {"agent": src, "ch": ch, "root": root, "task": task}})


def hand_back(agent, ch, root, ok, result, back):
    link = _link(ch, root)
    reply(back["ch"], back["root"], (f"📬 *#{agent} 회신* ({'완료' if ok else '실패'})" + (f" · <{link}|원문>" if link else "")
                                     + f"\n{result[:1500]}"))
    enqueue(back["agent"], back["ch"], back["root"], back["root"],
            f"[#{agent} 회신] 네가 넘긴 일(「{back['task']}」)의 결과다:\n{result[:3000]}\n"
            "이걸 반영해 원래 작업을 마무리하고 보고해. 다시 넘기지 마라(HANDOFF 금지).",
            {"depth": 1})


# ---------- 승인 카드 (2026-11-02: 승인 / 직접검토 / 거절) ----------
# 담당이 응답 끝에 「APPROVAL {json}」 줄을 남기면 → 증빙·정리 화면 이미지 + 금액 대조 결과 + 버튼 3개를 스레드에 올림
APPROVALS = HERE / "state" / "approvals.json"
CHOICE = {"approve": "✅ 승인", "review": "👀 직접검토", "reject": "❌ 거절"}
# 문서 반영 카드(팀장 지시 → .md 변경, 주인만): 승인/검토/거절 대신 두 버튼 (2026-11-04 사용자 요청 — 팀장님이 보기 편하게)
DOC_CHOICE = {"doc_apply": "✅ 바로 반영하기", "doc_vscode": "🛠️ VS Code에서 세부 작업 후 반영"}
DOC_WAIT = HERE / "output" / "문서반영_VS코드_대기.md"  # 「VS Code에서」를 고른 건 — VS Code 세션이 이 파일을 보고 이어서 반영


def parse_card(raw):
    """APPROVAL 줄의 JSON — 윈도우 경로의 홑 역슬래시는 JSON 위반이라 한 번 감싸 주고 다시 시도"""
    for text in (raw, re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', raw)):
        try:
            return json.loads(text)
        except ValueError:
            continue
    log.warning("승인 카드 JSON 못 읽음: %s", raw[:200])
    return None


def split_approvals(text):
    cards, keep = [], []
    for line in text.splitlines():
        m = re.match(r"^\s*`*\s*APPROVAL\s+(\{.*\})\s*`*\s*$", line)
        if m:
            card = parse_card(m[1])
            if card is not None:
                cards.append(card)
                continue
        keep.append(line)
    return "\n".join(keep).rstrip(), cards


def split_docnotes(text):
    """팀장 지시로 생긴 문서 변경 제안 — 「DOCNOTE {json}」 줄 (2026-11-04)"""
    notes, keep = [], []
    for line in text.splitlines():
        m = re.match(r"^\s*`*\s*DOCNOTE\s+(\{.*\})\s*`*\s*$", line)
        card = parse_card(m[1]) if m else None
        if card is not None:
            notes.append(card)
        else:
            keep.append(line)
    return "\n".join(keep).rstrip(), notes


def docnote_card(n):
    """DOCNOTE → 주인만 누르는 승인 카드. 승인 = 그 내용대로 문서 반영"""
    files = ", ".join(n.get("files") or []) or "(문서 미지정)"
    issue = str(n.get("issue", ""))
    summary = (f"📋 *팀장님 지시*: {n.get('instruction', '')}\n🗂️ *이렇게 정리*: {n.get('organized', '')}\n"
               f"{'⚠️' if '있음' in issue else '✅'} *문제*: {issue}\n"
               f"➡️ *앞으로*: {n.get('next', '')}\n📄 *반영할 문서*: {files}")
    return {"id": n.get("id"), "title": f"문서 반영 · {n.get('title', '')}", "summary": summary, "owner_only": True,
            "check": "팀장님 지시 작업은 끝났고, 호정님 작업 폴더 문서(.md) 반영만 남음",
            "action": f"문서 반영 — {files} 에 다음 내용: {n.get('edit', '')}"}


def post_approval(ch, root, agent, session, c):
    key = f"{session[:8]}-{str(c.get('id') or uuid.uuid4().hex[:6])[:8]}"
    with _lock:
        data = load(APPROVALS, {})
        data[key] = {"agent": agent, "session": session, "ch": ch, "root": root, **c, "state": "대기",
                     "at": f"{dt.datetime.now():%Y-%m-%d %H:%M}"}
        save(APPROVALS, data)
    shots = c.get("images") or ([c["image"]] if c.get("image") else [])
    shown = [i for i in shots if i and Path(i).is_file()]
    for i in shown:  # 담당이 넣은 순서대로 — 계산서·증빙이 먼저, 작성 화면이 뒤
        try:
            app.client.files_upload_v2(channel=ch, thread_ts=root, file=i, title=Path(i).name,
                                       initial_comment=f"🖼️ {c.get('title', '')} — {Path(i).name}")
        except Exception as e:
            log.warning("승인 이미지 업로드 실패 %s %s", i, e)
    if shown:
        time.sleep(4)  # 업로드 공유가 늦게 떠서 — 이미지가 버튼 카드보다 먼저 보이게
    text = f"🟡 *{'호정님 확인' if c.get('owner_only') else '승인 요청'} · {c.get('title', '')}*"
    text += f"\n🔍 대조: {c['check']}" if c.get("check") else "\n⚠️ 금액 대조 결과가 안 적혀 있어요 — 직접 확인 후 누르세요"
    if c.get("summary"):
        text += f"\n{c['summary']}"
    if not shown:
        text += "\n_(증빙 이미지 없음)_"
    elif len(shown) < len(shots):
        text += f"\n_(이미지 {len(shots) - len(shown)}장은 파일이 없어 못 올렸어요)_"
    if c.get("owner_only"):
        app.client.chat_postMessage(channel=ch, thread_ts=root, reply_broadcast=True, text=f"문서 반영 확인: {c.get('title', '')}", blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": DOC_CHOICE["doc_apply"]}, "style": "primary",
                 "action_id": "doc_apply", "value": key},
                {"type": "button", "text": {"type": "plain_text", "text": DOC_CHOICE["doc_vscode"]},
                 "action_id": "doc_vscode", "value": key}]}])
        return
    if c.get("action"):
        text += f"\n_「승인」을 누르면: {c['action']}_"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}},
              {"type": "actions", "elements": [
                  {"type": "button", "text": {"type": "plain_text", "text": CHOICE["approve"]}, "style": "primary",
                   "action_id": "approve", "value": key},
                  {"type": "button", "text": {"type": "plain_text", "text": CHOICE["review"]},
                   "action_id": "review", "value": key},
                  {"type": "button", "text": {"type": "plain_text", "text": CHOICE["reject"]}, "style": "danger",
                   "action_id": "reject", "value": key}]}]
    # reply_broadcast — 스레드 안에만 두면 묻혀서 못 봄(2026-11-04 손수식품 11/2 카드·포장보스 매출내역서 카드) → 채널에도 같이 보이게
    app.client.chat_postMessage(channel=ch, thread_ts=root, text=f"승인 요청: {c.get('title', '')}", blocks=blocks,
                                reply_broadcast=True)


def presser(uid, owner_only=False):
    """버튼 누른 사람의 호칭 — 누를 수 없는 사람이면 None. 승인 카드는 주인·팀장(2026-11-04 사용자 지시), 문서 반영은 주인만"""
    if uid == cfg.get("owner"):
        return "호정님"
    who = (cfg.get("members") or {}).get(uid, "")
    if not owner_only and who.startswith("팀장"):
        return who.strip() + "님"
    return None


def on_choice(ack, body, action):
    ack()
    key, kind = action["value"], action["action_id"]
    by = presser(body["user"]["id"], owner_only=load(APPROVALS, {}).get(key, {}).get("owner_only", False))
    if not by:
        return
    with _lock:
        data = load(APPROVALS, {})
        item = data.get(key)
        if not item or item.get("state") != "대기":
            return
        item["state"], item["by"] = LABEL[kind], by
        save(APPROVALS, data)
    log.info("승인 선택 %s %s", key, kind)
    ch, root, title = item["ch"], item["root"], item.get("title", "")
    done = f"{LABEL[kind]} · *{title}* — {by}"
    if item.get("check"):
        done += f"\n🔍 대조: {item['check']}"
    if item.get("summary"):
        done += f"\n{item['summary']}"
    app.client.chat_update(channel=ch, ts=body["message"]["ts"], text=f"{LABEL[kind]} · {title}",
                           blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": done}}])
    if kind == "doc_vscode":
        with _lock:
            DOC_WAIT.parent.mkdir(exist_ok=True)
            head = "" if DOC_WAIT.exists() else ("# 문서 반영 대기 (VS Code에서 세부 작업 후 반영)\n\n"
                                                 "슬랙 「VS Code에서 세부 작업 후 반영」을 누른 건. 반영 끝나면 그 항목을 지우고 슬랙 스레드에 알린다.\n")
            with DOC_WAIT.open("a", encoding="utf-8") as f:
                f.write(head + f"\n## {dt.datetime.now():%Y-%m-%d %H:%M} · #{item['agent']} · {title}\n"
                        f"{item.get('summary', '')}\n\n반영할 내용: {item.get('action', '')}\n"
                        f"슬랙 스레드: {_link(ch, root) or root}\n")
        reply(ch, root, f"🛠️ *{title}* — 호정님이 VS Code에서 세부 작업 후 반영할게요. "
                        f"(대기 목록: agents/shared/slack_bot/output/{DOC_WAIT.name})")
        return
    if kind in ("approve", "doc_apply"):
        enqueue(item["agent"], ch, body["message"]["ts"], root,
                f"{by}이 슬랙 버튼으로 「승인」을 눌렀다. 대상: {title} — {item.get('summary', '')}\n"
                f"이 건만 진행: {item.get('action') or '준비해 둔 다음 단계'}\n다른 건은 손대지 말고, 끝나면 결과를 짧게 보고.",
                {"broadcast": True})
    elif kind == "review":
        reply(ch, root, f"👀 *{title}* — 직접 검토하시도록 그대로 둘게요. 처리하신 뒤 이 스레드에 알려 주시면 이어서 할게요.")
    else:
        reply(ch, root, f"❌ *{title}* — 진행하지 않을게요. 거절 이유를 이 스레드에 적어 주시면 업무노트에 기록해 다음부터 반영할게요.")


LABEL = {**CHOICE, **DOC_CHOICE}
for _a in LABEL:
    app.action(_a)(on_choice)


# ---------- 일일 주문서 (2026-11-02: 파일 게시 + 「보냄」 버튼) ----------
# 사람이 카톡으로 보낸 뒤 버튼을 누르면 기록. 주문번호의 모든 출고처가 보냄이 되면 출고완료 대상으로 알림 (실행은 아직 사람)
SENT = REPO / "agents" / "inventory_sync" / "state" / "sent.json"


def post_order_batch(key, path, text, level):
    from notify import CHANNELS
    ch = CHANNELS[key]
    root = app.client.chat_postMessage(channel=ch, text=text)["ts"]
    for vendor, v in load(Path(path), {}).get("vendors", {}).items():
        f = Path(v["file"])
        comment = f"📄 *{vendor}* 주문서"
        if f.suffix == ".txt":
            comment += f"\n```{f.read_text(encoding='utf-8')[:2500]}```"
        app.client.files_upload_v2(channel=ch, thread_ts=root, file=str(f), title=f.name, initial_comment=comment)
        time.sleep(3)  # 파일이 버튼보다 먼저 보이게
        app.client.chat_postMessage(channel=ch, thread_ts=root, text=f"{vendor} 주문서", blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{vendor}* · {len(v['orders'])}주문 {v['rows']}행 — 보내신 뒤 눌러 주세요"}},
            {"type": "actions", "elements": [{"type": "button", "text": {"type": "plain_text", "text": "📨 보냄"}, "style": "primary",
                                              "action_id": "order_sent", "value": f"{path}|{vendor}"}]}])


@app.action("order_sent")
def on_order_sent(ack, body, action):
    ack()
    if not presser(body["user"]["id"]):
        return
    path, vendor = action["value"].rsplit("|", 1)
    ch, msg = body["channel"]["id"], body["message"]
    with _lock:
        data = load(Path(path), {})
        v = data["vendors"][vendor]
        v["sent"] = True
        save(Path(path), data)
        sent = {tuple(x) for x in load(SENT, [])} | {(o, vendor) for o in v["orders"]}
        save(SENT, sorted(sent))
    done = [o for o, vs in data["orders"].items() if vendor in vs and "확인 필요" not in vs and all((o, x) in sent for x in vs)]
    wait = [o for o in v["orders"] if o not in done]
    app.client.chat_update(channel=ch, ts=msg["ts"], text=f"보냄: {vendor}", blocks=[
        {"type": "section", "text": {"type": "mrkdwn", "text": f"✅ *{vendor}* 보냄 · {len(v['orders'])}주문"}}])
    text = f"📦 *{vendor}* 보냄 기록"
    if done:
        text += f"\n출고완료 가능 {len(done)}건: " + ", ".join(done[:20])
    if wait:
        text += f"\n다른 출고처를 기다리는 주문 {len(wait)}건: " + ", ".join(wait[:20])
    root = msg.get("thread_ts") or msg["ts"]
    real = [o for o in done if not o.startswith("시험")]
    reply(ch, root, text + ("\n마켓봄 출고완료 처리 중…" if real else ""))
    if real:  # 보냄 = 출고완료 승인 (사용자 지시 2026-11-04 「보내기 누른 건은 마켓봄 출고완료 처리까지」)
        threading.Thread(target=_ship_done, args=(ch, root, real), daemon=True).start()


SHIP_DONE = REPO / "agents" / "inventory_sync" / "scripts" / "ship_done.py"


def _ship_done(ch, root, orders):
    try:
        p = subprocess.run([sys.executable.replace("pythonw", "python"), "-X", "utf8", str(SHIP_DONE), *orders],
                           cwd=SHIP_DONE.parent, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = p.stdout.strip() or p.stderr.strip()[-800:]
        bad = p.returncode != 0 or "⚠️" in out
        reply(ch, root, ("⚠️ " if bad else "🚚 ") + "*마켓봄 출고완료*\n" + out)
        log.info("출고완료 %s → %s", orders, out.replace("\n", " / "))
        if bad:
            send("todo", f"⚠️ 마켓봄 출고완료 확인 필요 — {', '.join(orders)}\n{out}", "warn")
    except Exception as e:
        reply(ch, root, f"⚠️ 마켓봄 출고완료 실행 오류: {e} — 마켓봄에서 직접 처리해 주세요")


UPLOADS = HERE / "state" / "uploads"


def member_name(user):
    """슬랙 표시 이름 — users:read 권한이 없으면 사용자 ID"""
    try:
        u = app.client.users_info(user=user)["user"]
        return u.get("profile", {}).get("display_name") or u.get("real_name") or user
    except Exception:
        return user


def save_files(files, ts):
    """슬랙에 올린 캡처·파일을 PC로 받아 경로 목록 반환 (files:read)"""
    out = []
    token = keyring.get_password("slack-bot", "업무비서")
    for f in files:
        url = f.get("url_private_download") or f.get("url_private")
        if not url:
            continue
        UPLOADS.mkdir(parents=True, exist_ok=True)
        path = UPLOADS / f"{ts.replace('.', '_')}_{re.sub(r'[\\/:*?<>|]', '_', f.get('name', 'file'))}"
        try:
            r = requests.get(url, headers={"Authorization": "Bearer " + token}, timeout=60)
            r.raise_for_status()
            path.write_bytes(r.content)
            out.append(str(path))
        except Exception as e:
            log.warning("파일 받기 실패 %s %s", f.get("name"), e)
    return out


SEEN = HERE / "state" / "last_seen.json"  # 마지막으로 받은 슬랙 글 시각 — 연결이 끊겼다 살아나면 이 뒤의 글을 다시 읽음


def mark_seen(ts):
    with _lock:
        if float(ts) > float(load(SEEN, {"ts": "0"})["ts"]):
            save(SEEN, {"ts": ts})


@app.event("message")
def on_message(event, say):
    if event.get("ts"):
        mark_seen(event["ts"])
    agent = INSTRUCT.get(event.get("channel"))
    # thread_broadcast = 스레드 답글을 「채널에도 전송」 체크하고 보낸 것
    if event.get("subtype") not in (None, "file_share", "thread_broadcast") or event.get("bot_id") or not agent:
        return
    user, text = event.get("user"), (event.get("text") or "").strip()
    paths = save_files(event.get("files") or [], event["ts"]) if user else []
    if paths:
        text = (text or "올린 파일을 확인해줘") + "\n\n[사용자가 올린 파일]\n" + "\n".join(f"- {p}" for p in paths)
    if not cfg.get("owner"):
        cfg["owner"] = user  # 처음 쓴 사람을 주인으로 고정 (개인 워크스페이스)
        save(CONFIG, cfg)
        log.info("주인 등록 %s", user)
    if not user or not text:
        return
    if user != cfg["owner"]:  # 팀장·팀원 글 (2026-11-04) — 누가 썼는지 담당에게 알림. 호칭은 config/slack.json 「members」
        who = cfg.setdefault("members", {}).get(user)
        if not who:
            who = cfg["members"][user] = f"팀원 {member_name(user)}"
            save(CONFIG, cfg)
            log.info("새 구성원 %s → %s (호칭은 config/slack.json members 에서 바꿈)", user, who)
        role, _, name = who.partition(" ")
        text = f"[{role} {name}님 메시지]\n{text}"
    react(event["channel"], event["ts"], "hourglass_flowing_sand")
    q = enqueue(agent, event["channel"], event["ts"], event.get("thread_ts"), text)
    if q.unfinished_tasks > 1:
        say(text=f"⏳ #{agent}의 앞 작업 {q.unfinished_tasks - 1}건이 끝나면 시작할게요. (다른 담당 채널은 동시에 돼요)",
            thread_ts=event.get("thread_ts") or event["ts"])


# ---------- 메일 감시 (2026-10-29 정시 → 5분마다 / 2026-11-02 업무마다 주기·시간대 분리) ----------
# 감시 루프는 POLL_MIN 마다 깨고, 업무는 각자의 주기(분)가 지나고 각자의 실행 시간대 안일 때만 실행
# → 발주 자동입력은 월~금 09~18시 2시간마다(사용자 지시 2026-11-02), 계산서 수집은 월~금 07~21시 5분마다 (2026-11-05 사용자: 자동 실행은 월~금)
# 새 메일이 있을 때만 업무 채널에 알리고, 실패는 연속 실패의 첫 번째만 알림
POLL_MIN = 5  # 루프가 깨는 간격 — 가장 짧은 업무 주기와 같게 둔다
WINDOW_ALL = (5, 7, 21)    # (요일 상한, 시작 시, 끝 시) — 월~금 07~21시 (2026-11-05 토요일 제외). 루프가 도는 전체 시간대 = 업무 시간대의 합집합
WINDOW_ORDER = (5, 9, 18)  # 월~금 09~18시 — 발주 자동입력 (사용자 지시 2026-11-02 「월~금 9시~18시 매 2시간」)
WATCH = [  # (이름, 스크립트, 인자, 알림 채널 키 — None 이면 스크립트가 직접 알림, 실행 주기(분), 실행 시간대)
    ("발주 자동입력", REPO / "agents" / "order_intake" / "scripts" / "write_orders.py", ["--write"], "order", 120, WINDOW_ORDER),
    ("계산서 수집", REPO / "agents" / "expense_report" / "scripts" / "invoice_intake.py", [], None, 5, WINDOW_ALL),
]
WATCH_STATE = HERE / "state" / "watch_runs.json"  # 봇을 다시 켜도 주기가 처음부터 돌지 않게 마지막 실행 시각을 남김
_failing = set()


def in_window(window, now):
    """그 업무의 실행 시간대 안인지 — (요일 상한(이 요일 번호보다 작을 때만), 시작 시, 끝 시(배타))"""
    days, start, end = window
    return now.weekday() < days and start <= now.hour < end


def window_text(window):
    days, start, end = window
    return f"{'월~금' if days == 5 else '월~토'} {start:02d}~{end:02d}시"


def due(name, every, now):
    """지금 돌릴 차례인지 — 마지막 실행에서 주기(분)가 지났으면. 기록이 없으면 바로 실행"""
    last = load(WATCH_STATE, {}).get(name)
    if not last:
        return True
    try:
        # 루프 간격 때문에 매 회차 몇 초씩 밀리는 걸 감안해 30초 여유 (안 두면 1시간이 1시간 5분이 됨)
        return (now - dt.datetime.fromisoformat(last)).total_seconds() >= every * 60 - 30
    except ValueError:
        return True


def mark_run(name, now):
    with _lock:
        data = load(WATCH_STATE, {})
        data[name] = now.isoformat(timespec="seconds")
        save(WATCH_STATE, data)


def run_script(path, args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable.replace("pythonw", "python"), "-X", "utf8", str(path), *args],
                       cwd=path.parent, env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=15 * 60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    status = next((l[7:].strip() for l in reversed(p.stdout.splitlines()) if l.startswith("STATUS:")), "")
    return p.returncode, status, p.stdout, p.stderr


# ---------- 실행 현황판 (2026-10-30 사용자 요청: 자동 업무는 돌았는지·결과를 무조건 슬랙에) ----------
# 회차마다 새 글을 쓰면 하루 수십~수백 개가 쌓이므로, 채널마다 「오늘 자동 실행 현황」 글 하나를 매 실행마다 고쳐 씀
# (날이 바뀌면 새 글). 실제로 처리한 일이 있거나 실패하면 지금처럼 따로 새 글도 올림
BOARD = HERE / "state" / "status_board.json"


def _next_run(now, every, window):
    """다음 실행 시각 — 주기를 더한 시각이 그 업무의 시간대를 벗어나면 다음 실행일 시작 시각으로 적는다"""
    nxt = now + dt.timedelta(minutes=every)
    if nxt.date() == now.date() and nxt.hour < window[2]:
        return f"{nxt:%H:%M}"
    return f"다음 실행일 {window[1]:02d}:00"


def board(name, key, ok, status, every, window):
    from notify import CHANNELS
    ch = CHANNELS.get(key)
    if not ch:
        return
    now = dt.datetime.now()
    with _lock:
        data = load(BOARD, {})
        b = data.get(name)
        if not b or b.get("date") != f"{now:%Y-%m-%d}":
            b = {"date": f"{now:%Y-%m-%d}", "ts": None, "runs": 0, "work": 0, "fail": 0, "first": f"{now:%H:%M}"}
        b["runs"] += 1
        b["fail"] += 0 if ok else 1
        b["work"] += 1 if ok and not re.search(r"새 (메일|계산서) 0(통|건)", status) else 0
        b.update(last=f"{now:%H:%M}", status=status or "결과 없음", ok=ok)
        text = (f"{'🟢' if ok else '🔴'} *{name} — 오늘({now:%m/%d}) 자동 실행 현황*\n"
                f"마지막 실행 {b['last']} · {'정상' if ok else '실패'} · {b['status']}\n"
                f"오늘 {b['first']}부터 {b['runs']}회 실행 · 처리한 회차 {b['work']}회 · 실패 {b['fail']}회\n"
                f"_다음 실행 약 {_next_run(now, every, window)} "
                f"({window_text(window)}, {f'{every // 60}시간' if every % 60 == 0 and every >= 60 else f'{every}분'}마다)_")
        try:
            if b["ts"]:  # 현황판 뒤에 다른 글이 올라왔으면 옛 현황판을 지우고 맨 아래에 다시 씀
                after = app.client.conversations_history(channel=ch, oldest=b["ts"], limit=1)["messages"]
                if after:
                    app.client.chat_delete(channel=ch, ts=b["ts"])
                    b["ts"] = None
            if b["ts"]:
                app.client.chat_update(channel=ch, ts=b["ts"], text=text)
            else:
                b["ts"] = app.client.chat_postMessage(channel=ch, text=text)["ts"]
        except Exception as e:
            log.warning("현황판 실패 %s %s", name, e)
            b["ts"] = None  # 글이 지워졌으면 다음 회차에 새로 씀
        data[name] = b
        save(BOARD, data)


# ---------- 계산서 수집 → 노션 첨부 자동 이어하기 (2026-11-02 사용자 지시) ----------
# 「계산서 첨부해줘」라고 말하지 않아도, 새 계산서가 수집되면 담당이 노션 카드를 확인하고 조건이 맞으면 바로 댓글 첨부
PENDING_ATTACH = REPO / "agents" / "expense_report" / "state" / "pending_attach.json"
ATTACH_TASK = (
    "[자동] 방금 계산서 {n}건을 수집했습니다 ({who}). "
    "agents/expense_report/state/pending_attach.json 의 건마다 노션 「법인 지출통합결의서 확인용」 Master DB에서 "
    "카드를 찾아 **카드 금액 = 계산서 합계**를 대조하고, 카드가 있고 금액이 맞고 세금계산서 칸·댓글에 계산서가 아직 없으면 "
    "그 자리에서 카드 댓글에 첨부하세요(이 경우 승인 카드 없이 바로). 이미 있으면 「이미 있음」으로 목록에서 빼고, "
    "금액 불일치·어느 카드인지 모호하면 첨부하지 말고 「확인 필요」로 보고하세요. "
    "**카드가 없는데 그 건에 `statement`(같은 업체가 보낸 거래명세표 PDF·PNG)가 붙어 있으면** 확인 필요로 멈추지 말고 "
    "README §8 대로 거래명세표 ↔ 계산서 금액을 대조하고, 제때 운영 품목이면 발주진행현황 P·Q(제때 매입확정)와 명세서 수량까지 대조해, 다 맞으면 BT FLOW 지결을 작성완료 직전까지 채우고 "
    "승인 카드를 올리세요(승인 → 작성완료 → 노션 「확인용」 카드 생성 확인 → 계산서 첨부). "
    "카드도 명세표도 없으면 지금처럼 「확인 필요」 + 작성 대기 등록."
)


def _attach_uids():
    """(uid, 거래명세표 붙음) — 지난번 계산서에 명세표가 새로 짝지어져도 다시 맡기도록"""
    try:
        return {(r.get("uid"), bool(r.get("statement"))) for r in load(PENDING_ATTACH, [])}
    except Exception as e:
        log.warning("첨부 대기 목록 읽기 실패 %s", e)
        return set()


def auto_attach(before):
    """계산서 수집으로 새로 쌓인 건이 있으면 지결계산서담당에게 노션 첨부를 바로 맡긴다"""
    from notify import CHANNELS
    rows = [r for r in load(PENDING_ATTACH, []) if (r.get("uid"), bool(r.get("statement"))) not in before]
    ch = CHANNELS.get("invoice")
    if not rows or not ch:
        return
    who = ", ".join(dict.fromkeys(str(r.get("supplier") or "?") for r in rows))[:300]
    ts = app.client.chat_postMessage(
        channel=ch, text=f"🧾 새 계산서 {len(rows)}건 — 노션 카드 확인하고 조건이 맞으면 첨부할게요 ({who})")["ts"]
    enqueue("지결계산서담당", ch, ts, ts, ATTACH_TASK.format(n=len(rows), who=who))
    log.info("계산서 자동 첨부 지시 %s건 %s", len(rows), who)


def watch_once(now=None):
    now = now or dt.datetime.now()
    for name, path, args, key, every, window in WATCH:
        if not in_window(window, now) or not due(name, every, now):
            continue
        mark_run(name, now)  # 실행 전에 찍어 둠 — 오래 걸리거나 터져도 주기가 밀리지 않게
        before = _attach_uids() if name == "계산서 수집" else None
        try:
            code, status, out, err = run_script(path, args)
        except Exception as e:
            code, status, out, err = -1, "", "", str(e)
        board(name, key or "invoice", code == 0 and bool(status), status or (err or out).strip()[-120:], every, window)
        if code != 0 or not status:
            if name not in _failing:
                _failing.add(name)
                send(key or "invoice", f"❌ *{name} 실패* (오늘은 수동으로 확인)\n{(status or err or out)[-600:]}", "fail")
            log.warning("%s 실패 code=%s %s", name, code, (err or out)[-300:])
            continue
        if name in _failing:
            _failing.discard(name)
            send(key or "invoice", f"✅ {name} 다시 정상")
        if key and not re.search(r"새 메일 0통", status):
            body = "\n".join(l for l in out.splitlines() if l.startswith("|") or l.startswith("⚠️"))
            level = "warn" if "확인 필요" in status else "ok"
            send(key, f"{'⚠️' if level == 'warn' else '✅'} *{name}* · {status}\n{body}"[:3500], level)
        if before is not None:
            try:
                auto_attach(before)
            except Exception as e:
                log.warning("계산서 자동 첨부 지시 실패 %s", e)
        log.info("%s %s", name, status)


# 하루 한 번 아침 작업 (2026-10-30 사용자 요청: 전날 매입 확정분 → 발주진행현황 입고확인). 결과는 매번 담당 채널에
DAILY = [  # (이름, 스크립트, 인자, 채널 키, 시작 시각)
    # 08:10 재고·매출 갱신 뒤 종합현황 특이사항만 (읽기 전용, 2026-11-05 사용자 지시) — 갱신이 안 끝났으면 스크립트가 최대 8분 기다림
    ("종합현황 점검", REPO / "agents" / "jette_daily" / "scripts" / "summary_check.py", [], "stock", (8, 20)),
    ("입고확인 입력", REPO / "agents" / "order_intake" / "scripts" / "fill_receipts.py", ["--write"], "closing", (8, 30)),
    ("출고전 주문 분류", REPO / "agents" / "inventory_sync" / "scripts" / "daily_orders.py", [], "inventory", (9, 0)),
    ("원장 차감안", REPO / "agents" / "inventory_sync" / "scripts" / "ledger_daily.py", [], "ledger", (9, 10)),  # 재고통합담당 채널 (2026-11-04 분리)
]
WEEKDAYS_ONLY = {"출고전 주문 분류", "원장 차감안", "종합현황 점검"}  # 월~금 (토요일 제외) — 종합현황은 08:10 갱신이 월~금이라 (2026-11-05)
DAILY_STATE = HERE / "state" / "daily_runs.json"


def daily_once(now):
    done = load(DAILY_STATE, {})
    for name, path, args, key, (h, m) in DAILY:
        if name in WEEKDAYS_ONLY and now.weekday() >= 5:
            continue
        if done.get(name) == f"{now:%Y-%m-%d}" or (now.hour, now.minute) < (h, m):
            continue
        try:
            code, status, out, err = run_script(path, args)
        except Exception as e:
            code, status, out, err = -1, "", "", str(e)
        ok = code == 0 and bool(status)
        body = "\n".join(l for l in out.splitlines() if l.lstrip().startswith(("*", "•", "- ")))
        batch = re.search(r"^BATCH: (.+)$", out, re.M)
        if ok:
            level = "warn" if "확인 필요" in status else "ok"
            text = f"{'⚠️' if level == 'warn' else '✅'} *{name}* · {status}\n{body}"[:3500]
            if batch:
                post_order_batch(key, batch[1].strip(), text, level)
            else:
                send(key, text, level)
        else:
            send(key, f"❌ *{name} 실패* (오늘은 수동으로 확인)\n{(status or err or out)[-600:]}", "fail")
        done[name] = f"{now:%Y-%m-%d}"
        save(DAILY_STATE, done)
        log.info("%s %s", name, status or code)


# 날짜 지정 작업 (2026-11-04): state/schedule.json 의 [{"at": "YYYY-MM-DD HH:MM", "agent": "담당 이름", "task": "…"}]
# 시각이 지나면 그 담당 채널에 글을 올리고 담당이 그 글 스레드에서 작업 — 한 번만 (끝나면 "done" 기록)
SCHEDULE = HERE / "state" / "schedule.json"


def schedule_once(now):
    with _lock:
        jobs = load(SCHEDULE, [])
        due = [j for j in jobs if not j.get("done") and j.get("at", "9999") <= f"{now:%Y-%m-%d %H:%M}"]
        for j in due:
            j["done"] = f"{now:%Y-%m-%d %H:%M}"
        if due:
            save(SCHEDULE, jobs)
    for j in due:
        ch = _channel_of(j["agent"])
        if not ch:
            log.warning("예약 작업 담당 없음 %s", j)
            continue
        post = app.client.chat_postMessage(channel=ch, text=f"⏰ *예약 작업* ({j['at']})\n{j['task']}")
        enqueue(j["agent"], ch, post["ts"], None, f"[예약 작업 — 호정님이 미리 맡겨 둔 일] {j['task']}")
        log.info("예약 작업 %s → %s", j["at"], j["agent"])


# 매월 정기 루틴 (2026-11-04 사용자): 매월 5·6·7일 12:30, 그날이 주말이면 다음 월요일로 — 겹치면 그날 한 번만
# 6·7일 회차는 세금계산서 발행 확인·포장보스 신청 첨부까지 이어 가기 위함. 지시문은 「진행 상태부터 확인하고 다음 단계만」이라 여러 번 돌아도 안전
MONTHLY_STATE = HERE / "state" / "monthly_runs.json"


def _pojangboss_task(month, rounds):
    return (f"[월 정기 루틴 · {'·'.join(f'{d}일' for d in rounds)} 회차] 포장보스(리우) {month} 본부수익금 월 마감.\n"
            "settlements/리우/README.md 「월 마감 루틴」 1~9단계를 **진행 상태부터 확인하고 이어서** 한다 — 이미 끝난 단계"
            "(statements 원본·검토서·매출내역서 행·발행본 계산서 이미지·포장보스 신청)는 건너뛰고 다음 단계만. 브랜드 4개(옥된장·석문어·정백선·육직구) 모두.\n"
            "- 신청 화면에 그 달 행이 없으면 「미확정」으로 두고 다음 회차에 다시 본다(포장보스는 5일 이후 확정). 7일 회차에도 없으면 리우 생성 요청 문안 준비\n"
            "- 순서(사용자 2026-11-05): 매출내역서는 **BT FLOW /sales-issue 에서 작성**(노션에 직접 만들지 않음) → 노션 「법인 매출 내역서」에 생긴 행이 잘 작성됐는지 검토 → "
            "재무팀이 보통 1~2일 뒤 계산서를 발행해 그 행 「매출증빙」에 첨부 → 그 계산서를 포장보스 「신청하기」의 계산서 첨부란에 넣는다\n"
            "- 매출내역서는 지결처럼(사용자 2026-11-05): BT FLOW에 「매출 발행 요청하기」 **직전까지 입력** → 입력 화면 캡처·금액 대조로 브랜드별 승인 카드(APPROVAL) "
            "→ 「승인」을 받으면 같은 값으로 다시 채워 최종 제출. 포장보스 신청하기도 승인 카드로. 계산서가 아직 안 붙었으면 「발행 대기」로 보고하고 다음 회차에 다시 본다\n"
            f"- 포장보스 자료(1~3단계)는 `python -X utf8 settlements/리우/scripts/fetch_month.py {month}` — 저장된 계정으로 스크립트가 직접 로그인. "
            "크롬은 BT FLOW·노션·포장보스 「신청하기」에만 쓰고, 그 로그인이 풀려 있으면 멈추고 「로그인 필요」로 보고\n"
            f"- **브랜드 모두 포장보스 신청까지 끝나면** `agents/shared/slack_bot/state/monthly_done.json` 에 {{\"포장보스 매출 수수료 월 마감\": \"{month}\"}} 을 기록한다 → 이번 달 남은 회차는 돌지 않는다\n"
            "끝에 브랜드별 진행표 한 장(검증 / 매출내역서 / 계산서 / 신청)과 금액(지급 확정, VAT 포함).")


MONTHLY = [  # (이름, 담당, 매월 날짜, 시각, 지시문(대상월 YYYY-MM, 회차 날짜들))
    # 5~10일 — 재무팀 계산서가 1~2일 늦게 붙으므로 신청까지 따라가되, 다 끝나면 monthly_done.json 으로 멈춤 (2026-11-05)
    ("포장보스 매출 수수료 월 마감", "매출수수료담당", (5, 6, 7, 8, 9, 10), (12, 30), _pojangboss_task),
]
MONTHLY_DONE = HERE / "state" / "monthly_done.json"  # 담당이 「이번 달 끝」을 적는 곳 {이름: "YYYY-MM"}


def monthly_runs(year, month, days):
    """그 달 실행일 → [원래 날짜]. 주말이면 다음 평일로 밀되, 회차끼리 같은 날로 겹치지 않게 앞 회차 다음 평일로
    (예: 5·6일이 토·일 → 7(월)·8(화)·9(수) — 6·7일 회차의 계산서 확인 기회를 잃지 않게)"""
    out, last = {}, None
    for d in days:
        run = dt.date(year, month, d)
        if last and run <= last:
            run = last + dt.timedelta(days=1)
        while run.weekday() >= 5:
            run += dt.timedelta(days=1)
        out[run], last = [d], run
    return out


def monthly_once(now):
    done = load(MONTHLY_STATE, {})
    for name, agent, days, (h, m), task in MONTHLY:
        # PC가 그 시각(또는 그날 하루 종일) 꺼져 있었으면 켜졌을 때 밀린 회차를 한 번에 돈다 (2026-11-05 사용자 지시)
        last = done.get(name, "")
        today = now.date()
        runs = {run: ds for run, ds in monthly_runs(now.year, now.month, days).items()
                if str(run) > last and (run < today or (run == today and (now.hour, now.minute) >= (h, m)))}
        rounds = [d for ds in runs.values() for d in ds]
        if not rounds:
            continue
        ch = _channel_of(agent)
        if not ch:
            continue
        prev = (now.date().replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
        if load(MONTHLY_DONE, {}).get(name) == prev:  # 이번 달(전월분) 이미 끝남
            continue
        post = app.client.chat_postMessage(channel=ch, text=f"🗓️ *월 정기 루틴 · {name}* ({prev}분, {'·'.join(f'{d}일' for d in rounds)} 회차)")
        enqueue(agent, ch, post["ts"], None, task(prev, rounds))
        done[name] = str(max(runs))  # 처리한 회차의 실행일 — 오늘 날짜로 적으면 오늘 늦게 잡힌 다음 회차가 빠짐
        save(MONTHLY_STATE, done)
        log.info("월 정기 루틴 %s %s %s", name, prev, rounds)


def watcher():
    while True:
        now = dt.datetime.now()
        if in_window(WINDOW_ALL, now):  # 업무별 시간대는 watch_once 안에서 다시 확인
            daily_once(now)
            watch_once(now)
            schedule_once(now)
            monthly_once(now)
        time.sleep(POLL_MIN * 60)


def single_instance():
    """PC에 봇이 하나만 뜨게 — 로컬 포트를 잠금으로 씀. 이미 떠 있으면 조용히 종료"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 47321))
    except OSError:
        log.info("이미 실행 중인 봇이 있어 종료")
        raise SystemExit(0)
    return s  # 프로세스가 살아 있는 동안 잡고 있어야 함


# ---------- 슬랙 연결 끊김 대비 (2026-11-04) ----------
# 11/4 13:26 PC 네트워크가 잠깐 끊긴 뒤 수신 연결만 10초마다 재접속 실패를 반복 — 타이머 일은 돌아서 겉으론 멀쩡해 보였고,
# 그 사이 사용자 답글(이엘비티)을 못 받음. 슬랙은 놓친 글을 다시 보내 주지 않는다
# → 3분째 끊겨 있으면 restart-bot.ps1 로 스스로 재시작 + 다시 켜질 때 끊긴 사이 글을 직접 읽어 처리

def catch_up():
    try:
        _catch_up()
    except Exception as e:
        log.warning("놓친 글 처리 실패 %s", e)


def _catch_up():
    since = load(SEEN, {}).get("ts")
    if not since:
        return
    floor = max(float(since), time.time() - 86400)  # 하루 넘게 지난 글은 다시 처리하지 않음
    me = app.client.auth_test()["user_id"]
    found = {}
    for ch in INSTRUCT:
        try:
            hist = app.client.conversations_history(channel=ch, oldest=str(floor - 7 * 86400), limit=200)["messages"]
            for m in hist:
                if float(m["ts"]) > floor:
                    found[(ch, m["ts"])] = m
                if float(m.get("latest_reply", 0)) > floor:
                    for r in app.client.conversations_replies(channel=ch, ts=m["ts"], oldest=str(floor), limit=200)["messages"]:
                        if r["ts"] != m["ts"] and float(r["ts"]) > floor:
                            found[(ch, r["ts"])] = r
        except Exception as e:
            log.warning("놓친 글 읽기 실패 %s %s", ch, e)
    for (ch, ts), m in sorted(found.items(), key=lambda x: float(x[0][1])):
        if m.get("bot_id") or any(me in r.get("users", []) for r in m.get("reactions", [])):
            continue  # 봇 글, 이미 받은 글(봇이 ⏳·👀 표시를 단 글)
        if m.get("subtype") not in (None, "file_share", "thread_broadcast"):
            continue  # 채널 이름 변경·입장 같은 시스템 메시지 (11/5 채널명 변경 글에 답하려다 cannot_reply_to_message)
        log.info("놓친 글 처리 %s %s", ch, ts)
        try:
            app.client.chat_postMessage(channel=ch, thread_ts=m.get("thread_ts") or ts,
                                        text="⏪ 봇 연결이 끊겨 있던 사이 남기신 글이라 지금 이어서 처리할게요.")
            on_message(dict(m, channel=ch), lambda text, thread_ts, ch=ch: app.client.chat_postMessage(
                channel=ch, text=text, thread_ts=thread_ts))
        except Exception as e:  # 한 건이 실패해도 나머지 놓친 글은 계속
            log.warning("놓친 글 처리 실패 %s %s %s", ch, ts, e)


def socket_watchdog(handler):
    bad = 0
    while True:
        time.sleep(60)
        try:
            bad = 0 if handler.client.is_connected() else bad + 1
        except Exception:
            bad += 1
        if bad >= 3:
            log.warning("슬랙 수신 연결이 3분째 끊김 — restart-bot.ps1 로 재시작")
            flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP — 봇이 꺼져도 재시작 스크립트는 계속
            args = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", str(HERE / "restart-bot.ps1")]
            try:
                subprocess.Popen(args, creationflags=flags | 0x01000000)  # + CREATE_BREAKAWAY_FROM_JOB
            except OSError:
                subprocess.Popen(args, creationflags=flags)
            return


def main():
    _lock = single_instance()  # noqa: F841
    # 채널은 ID로 기억(setup_channels.py) — 채널 이름을 바꿔도 그대로 동작
    ids = cfg.get("channels", {})
    INSTRUCT.update({ids[n]: n for n, a in AGENTS.items() if a.get("지시") and n in ids})
    if not INSTRUCT:
        raise SystemExit("지시 받을 채널이 없음 — setup_channels.py 먼저 실행")
    recover_pending()
    work_board.clear("슬랙")  # 지난 봇이 남긴 표시 — 복구되는 작업은 이어서 돌지만 표시는 다시 달지 않음
    threading.Thread(target=watcher, daemon=True).start()
    log.info("봇 시작 — 담당 %s", ", ".join(INSTRUCT.values()))
    handler = SocketModeHandler(app, keyring.get_password("slack-bot", "app-token"))
    threading.Thread(target=socket_watchdog, args=(handler,), daemon=True).start()
    threading.Timer(30, catch_up).start()  # 연결이 붙은 뒤에
    handler.start()


if __name__ == "__main__":
    main()
