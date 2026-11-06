# agents/ 안에 쌓이는 백업·지난 결과·내려받은 파일을 agents/_삭제대상/YYMMDD/ 로 옮긴다 (2026-11-05 사용자 지시)
# 「반드시 있어야 동작하는 파일이 아니면 혼선 생기지 않게 삭제 대상 폴더로 — 정리해 가면서 관리」
# 지우지는 않는다 — _삭제대상/ 은 사용자가 보고 직접 비운다. 원래 경로를 그대로 살려 옮기므로 필요하면 되돌릴 수 있다
#
# 실행: python -X utf8 cleanup.py            (미리보기 — 옮길 목록만)
#       python -X utf8 cleanup.py --move     (실제로 옮김)
# 자동 실행: 슬랙 봇 「하루 한 번 아침 작업」 DAILY 「파일 정리」 — 월~금 08:00, 슬랙 알림 없음(실패만 #공통_작업완료) (2026-11-05)

import argparse
import datetime as dt
import json
import shutil
import time
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1]
TRASH = AGENTS / "_삭제대상"
DAY = 86400


def older(p, days):
    return time.time() - p.stat().st_mtime > days * DAY


def pending_sessions():
    try:
        return {j["session"] for j in json.loads((AGENTS / "shared/slack_bot/state/pending.json").read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return set()


def candidates():
    """(경로, 이유). 규칙 = 동작에 쓰이는 기간만 남기고 나머지"""
    out = []
    S = AGENTS / "shared/slack_bot/state"
    # 1) 고치기 전 백업(시트·문서·설정) — 되돌릴 때만 쓰는 파일. 나이와 상관없이 옮김(_삭제대상에 남아 있으니 되돌리기는 가능)
    for st in AGENTS.glob("*/state"):
        for p in st.glob("*.json"):
            if "백업" in p.stem or p.stem.endswith(("전_261", "전")) or "_수정전_" in p.stem or "전_26" in p.stem:
                out.append((p, "고치기 전 백업"))
    for p in S.glob("*백업*"):
        out.append((p, "고치기 전 백업"))
    for p in (S / "doc_backup").glob("*") if (S / "doc_backup").exists() else []:
        out.append((p, "문서 백업"))
    # 2) 제때 일일 조회 미리보기·백업 — 최근 3회분만
    J = AGENTS / "jette_daily/state"
    for pat in ("*_preview.json", "*_backup.json"):
        for p in sorted(J.glob(pat))[:-3]:
            out.append((p, "지난 회차 미리보기·백업(최근 3회분만 남김)"))
    # 3) 봇 결과 파일 — 재시작 복구용. 진행 중이 아니고 3일 지난 것
    busy = pending_sessions()
    for p in (S / "out").glob("*.json"):
        if p.name.split("_")[0] not in busy and older(p, 3):
            out.append((p, "지난 작업 결과(3일 지남)"))
    # 4) 슬랙에서 받은 캡처·파일 — 같은 스레드 후속 답글을 위해 7일 (2026-11-05 14일 → 7일, 사용자)
    for p in (S / "uploads").glob("*"):
        if older(p, 7):
            out.append((p, "슬랙 첨부(7일 지남)"))
    # 5) 마켓봄에서 내려받은 주문 엑셀 — 다시 받을 수 있음, 3일
    for p in (AGENTS / "inventory_sync/state/raw").glob("*"):
        if older(p, 3):
            out.append((p, "내려받은 원본(3일 지남, 다시 받을 수 있음)"))
    # 6) 출고 묶음 정보·주문서 산출물 — 「보냄」 버튼 기간 14일
    for p in (AGENTS / "inventory_sync/state/batches").glob("*.json"):
        if p.stem == "시험" or older(p, 14):
            out.append((p, "지난 출고 묶음(14일 지남)"))
    for p in (AGENTS / "inventory_sync/output").glob("*"):
        if older(p, 14):
            out.append((p, "지난 주문서 파일(14일 지남)"))
    # 6-1) 카톡 캡처 — 판별용 화면 캡처, 3일 (2026-11-06)
    for p in (AGENTS / "shared/kakao_intake/state/shots").glob("*.png"):
        if older(p, 3):
            out.append((p, "카톡 캡처(3일 지남)"))
    # 7) 시험용 폴더
    for p in [AGENTS / "expense_report/state/nts_test"]:
        if p.exists():
            out.append((p, "시험용"))
    # 8) 실행 로그 — 날짜별 파일만, 30일 (bot.log·restart.log 같은 단일 로그는 그대로)
    for d in AGENTS.glob("*/logs"):
        for p in d.glob("*"):
            if p.is_file() and p.name[:2] == "26" and older(p, 30):
                out.append((p, "지난 실행 로그(30일 지남)"))
    return [(p, why) for p, why in dict.fromkeys(out) if p.exists()]


def size(p):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--move", action="store_true")
    a = ap.parse_args()
    items = candidates()
    dest_root = TRASH / f"{dt.date.today():%y%m%d}"
    total = 0
    for p, why in items:
        total += size(p)
        rel = p.relative_to(AGENTS)
        print(f"{'옮김' if a.move else '대상'}  {rel}  ({why})")
        if a.move:
            dest = dest_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                dest = dest.with_name(f"{dest.stem}_{int(time.time())}{dest.suffix}")
            shutil.move(str(p), str(dest))
    print(f"STATUS: {len(items)}개 · {total / 1048576:.1f}MB {'→ _삭제대상/' + dest_root.name if a.move else '(미리보기)'}")


if __name__ == "__main__":
    main()
