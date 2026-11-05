# 작성 대기 지결의 증빙(거래명세서) 도착 감지 → 슬랙 알림
# 실행: python -X utf8 evidence_watch.py          (run-invoice-intake.ps1 이 계산서 수집 뒤에 이어서 호출)
#       python -X utf8 evidence_watch.py --list   (대기 목록만 보기)
#
# 규칙 (2026-10-30 사용자 지시)
#   · 거래명세서가 있어야만 지결을 올릴 수 있다
#   · 예외: 세금계산서에 '입고 일자별로' 품명·수량·단가가 모두 적혀 있으면 그 계산서가 명세서를 대체한다
#     (품목 한 줄 뭉뚱그림·수량/단가 공란·월 합계만 = 대체 불가)
#     → 계산서만 들어온 경우는 「확인 필요」로 올리고, 조건 충족 여부는 사람이·Claude 가 이미지로 확인한다
#
# 대기 목록: state/pending_expense.json  (거래처·금액·이체요청일·필요 증빙)
# 감지 대상: 바탕화면 「지출결의 증빙 이미지」 폴더에 새로 생긴 파일 + state/pending_attach.json(계산서 메일 수신분)
# 이 스크립트는 알리기만 한다 — BT FLOW 작성·상신은 하지 않는다

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared" / "slack_bot"))
from notify import send  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
STATE = HERE / "state"
WAITING = STATE / "pending_expense.json"
PENDING_ATTACH = STATE / "pending_attach.json"
EVID_DIR = Path.home() / "Desktop" / "지출결의 증빙 이미지"


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path, data):
    STATE.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def classify(stem, keywords, month):
    """파일 이름이 「업체약칭 + 월」 규칙에 맞는지 — 맞으면 ('거래명세서'|'세금계산서', 약칭), 아니면 (None, None)"""
    for kw in keywords:
        m = re.match(rf"^{re.escape(kw)}(\d+)(-\d+)?$", stem, re.IGNORECASE)
        if not m:
            continue
        digits = m[1]
        if digits == str(month):
            return "거래명세서", kw
        if digits == f"{month}0":
            return "세금계산서", kw
    return None, None


def scan_folder(item):
    """증빙 폴더에서 이 건의 증빙으로 보이는 파일 찾기 (등록일 이후에 생긴 것만)"""
    if not EVID_DIR.exists():
        return []
    added = dt.datetime.strptime(item["added"], "%Y-%m-%d").timestamp()
    kws, month = item["match"], item["month"]
    hits = []
    for p in EVID_DIR.iterdir():
        if p.is_dir() or p.stat().st_mtime < added:
            continue
        kind, kw = classify(p.stem, kws, month)
        if kind:
            hits.append({"file": p.name, "kind": kind})
        elif any(k.lower() in p.stem.lower() for k in kws):
            hits.append({"file": p.name, "kind": "후보(이름 규칙 밖)"})
    return hits


def scan_invoice_mail(item):
    """계산서 메일 수신분(pending_attach.json)에서 이 거래처 건 찾기"""
    out = []
    for x in load(PENDING_ATTACH, []):
        sup = (x.get("supplier") or "").replace(" ", "")
        if any(k.replace(" ", "") in sup for k in item["match"]):
            out.append({"supplier": x.get("supplier"), "kind": x.get("kind"),
                        "total": x.get("total"), "png": x.get("png"), "received": x.get("received")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="대기 목록만 출력")
    a = ap.parse_args()

    waiting = load(WAITING, [])
    # 이미 작성했거나 상신한 건은 다시 알리지 않음 — 담당이 done 대신 status 글자만 바꿔 두는 경우가 있음
    # (2026-11-04 이티엘비: 16:53 상신 완료인데 17:00에 「지결 마무리 가능」으로 또 알림)
    open_items = [x for x in waiting if not x.get("done")
                  and not any(w in x.get("status", "") for w in ("상신 완료", "작성완료 직전"))]

    if a.list:
        for x in waiting:
            mark = "완료" if x.get("done") else ("감지됨" if x.get("found") else "대기")
            print(f"[{mark}] {x['vendor']} {x['amount']:,}원 · 이체 {x['pay_date']} · 필요: {x['need']}")
        return

    ready, still = [], 0
    for item in open_items:
        folder, mail = scan_folder(item), scan_invoice_mail(item)
        statement = [h for h in folder if h["kind"] == "거래명세서"]
        if not (folder or mail):
            still += 1
            continue
        key = sorted([h["file"] for h in folder] + [m.get("png") or m.get("supplier") for m in mail])
        if item.get("found") == key:   # 이미 알린 것은 다시 알리지 않음
            continue
        item["found"] = key
        item["found_at"] = f"{dt.datetime.now():%Y-%m-%d %H:%M}"
        ready.append((item, folder, mail, bool(statement)))

    if ready:
        lines = [f"📄 *작성 대기 지결 {len(ready)}건 — 증빙 들어왔어요*"]
        for item, folder, mail, has_stmt in ready:
            lines.append(f"• *{item['vendor']}* {item['amount']:,}원 · 이체요청일 {item['pay_date']} · {item['detail']}")
            for h in folder:
                lines.append(f"    └ 폴더: {h['file']} ({h['kind']})")
            for m in mail:
                amt = f" {m['total']:,}원" if m.get("total") else ""
                lines.append(f"    └ 메일: {m['supplier']}{amt} ({m['kind']}, {m.get('received', '')})")
                gap = m["total"] - item["amount"] if m.get("total") else 0
                if gap:
                    lines.append(
                        f"       ⚠️ 대기 금액과 {abs(gap):,}원 차이 "
                        f"(대기 {item['amount']:,} ← 마감시트 / 계산서 {m['total']:,}). "
                        "**증빙(거래명세서·계산서)이 기준** — 마감시트에 반품·상계가 덜 반영됐을 수 있음"
                    )
            if has_stmt:
                lines.append("    → 거래명세서 확인됨. 지결 마무리 가능")
            else:
                lines.append("    → ⚠️ 거래명세서 없음. 계산서에 **입고 일자별** 품명·수량·단가가 다 있어야 대체 가능 — 확인 필요")
        lines.append(f"→ #공통_지결_계산서 에 「{ready[0][0]['vendor']} 지결 마무리해줘」 라고 쓰면 작성완료 직전까지 채울게요")
        msg = "\n".join(lines)
        level = "ok" if all(r[3] for r in ready) else "warn"
        send("invoice", msg, level)
        print(msg)
        save(WAITING, waiting)
    else:
        print(f"새 증빙 없음 · 대기 {still}건")

    print(f"STATUS: 완료 · 증빙 도착 {len(ready)}건 · 계속 대기 {still}건")


if __name__ == "__main__":
    main()
