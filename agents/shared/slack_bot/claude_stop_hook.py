# Claude Code Stop 훅 — 세션이 응답을 끝내면 슬랙 #클로드-세션 으로 알림
# 등록: ~/.claude/settings.json hooks.Stop (이 PC 전체 세션). stdin 으로 훅 입력 JSON을 받음
# 짧은 대답(MIN_SECONDS 미만)은 알리지 않음 — 오래 걸린 작업만. 실패해도 조용히 종료(세션을 막지 않음)

import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notify import send  # noqa: E402

MIN_SECONDS = 60
REPO = Path(r"C:\Users\BLUETREND\류호정\bt")


def parse_ts(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def last_turn(transcript):
    """마지막 사람 입력 시각, 그 뒤 마지막 assistant 글"""
    started, text = None, ""
    for line in transcript.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        msg = e.get("message") or {}
        content = msg.get("content")
        if e.get("type") == "user" and not e.get("isSidechain") and not e.get("isMeta"):
            # 도구 결과(tool_result)·스킬 본문(isMeta)은 사람 입력이 아님
            if (e.get("origin") or {}).get("kind", "human") == "human" and (
                    isinstance(content, str) or (isinstance(content, list) and
                                                 any(c.get("type") == "text" for c in content if isinstance(c, dict)))):
                started, text = parse_ts(e.get("timestamp")), ""
        elif e.get("type") == "assistant" and not e.get("isSidechain") and isinstance(content, list):
            t = "".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
            if t.strip():
                text = t
    return started, text


def main():
    data = json.loads(sys.stdin.read() or "{}")
    if data.get("stop_hook_active") or os.environ.get("CLAUDE_FROM_SLACK"):
        return  # 슬랙 #지시 작업은 봇이 스레드로 직접 답함 — 중복 알림 방지
    tp = Path(data.get("transcript_path") or "")
    if not tp.is_file():
        return
    started, text = last_turn(tp)
    text = data.get("last_assistant_message") or text
    if started:
        took = (dt.datetime.now(dt.timezone.utc) - started).total_seconds()
        if took < MIN_SECONDS:
            return
    cwd = Path(data.get("cwd") or ".")
    try:
        where = str(cwd.relative_to(REPO)).replace("\\", "/") or "bt(루트)"
    except ValueError:
        where = cwd.name
    summary = " ".join(text.split())
    if len(summary) > 300:
        summary = summary[:300] + "…"
    mins = f" · {int(took // 60)}분" if started else ""
    send("claude", f"✅ *[{where}]* 작업 끝남{mins}\n{summary}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
