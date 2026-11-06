# 월말 마감 요청 대상 고르기 (2026-11-06 사용자 기준 — README §11)
# 봇이 단계별로 지결계산서담당에게 맡길 때 담당이 먼저 실행한다. 사람·카톡 판단은 담당 몫, 이 스크립트는 「누구에게 지금 요청할 차례인가」만
#
#   python -X utf8 agents/expense_report/scripts/closing_targets.py plan                 # 이번 달 단계 날짜표
#   python -X utf8 agents/expense_report/scripts/closing_targets.py targets early        # 단계별 대상 (early / all / lastday / deadline / followup)
#   python -X utf8 agents/expense_report/scripts/closing_targets.py mark "씨에버상사" 요청 "2026-11-27 10:05 카톡"   # 진행 기록
#   python -X utf8 agents/expense_report/scripts/closing_targets.py status               # 업체별 진행표
#
# 단계 (말일 L, 주말이면 앞 금요일로 당김)
#   payday   P-3영업일 10:00 — 결제일 「당월 말일」 업체 원장 먼저 (2026-11 = 11/25)
#   early    L-3 10:00  — 당월 제때 입고 일정이 끝난 업체(+ 아직 요청 못 한 말일 결제 업체): 「당월 입고 종료되었습니다. ○월 마감원장 부탁드립니다」
#   all      L-1 15:30  — 아직 요청 안 한 당월 입고 업체 전체(말일 입고 업체 제외)
#   lastday  L   09:30  — 말일에 입고가 있는 업체
#   deadline P-1 09:00  — 말일 결제 업체 중 계산서가 아직 없는 곳: 「○일 12시까지 발행 시 말일 결제, 안 되면 다음 결제 주기」 (P = 말일 결제일)
#   followup 매 회차    — 요청했는데 원장 검토·계산서 요청이 안 끝난 업체 (회신 확인 → 검토 → 계산서 요청)

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE.parent / "state"
sys.path.insert(0, str(HERE.parents[1] / "shared"))
import gsheet  # noqa: E402

DAILY = "1x1KueQVbAyKYQJV_3pkcHZhJc5YJqjSbadiCIr3tRns"
SKIP_PAY = ("선결제", "당일결제")  # 월말 마감장 요청 대상 아님


def norm(s):
    return re.sub(r"[\s()（）㈜]|주식회사|\(주\)", "", str(s))


def biz_back(d):
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def biz_minus(d, n):
    """d에서 평일 n일 전"""
    while n > 0:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def month_end(today):
    nxt = (today.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return nxt - dt.timedelta(days=1)


def plan(today):
    L = month_end(today)
    P = biz_back(L)  # 말일 결제일 — 재무팀이 휴일이면 앞으로 옮김(캘린더 「지출결의」가 원본, 다르면 담당이 캘린더 기준으로)
    return {
        "payday": (biz_minus(P, 3), (10, 0)),  # 말일 결제 업체 원장 먼저 — 결제일 2일 전 마감·전날 12시 계산서 첨부를 맞추려면 3영업일 전 요청
        "early": (biz_back(L - dt.timedelta(days=3)), (10, 0)),
        "all": (biz_back(L - dt.timedelta(days=1)), (15, 30)),
        "lastday": (biz_back(L), (9, 30)),
        "deadline": (biz_back(P - dt.timedelta(days=1)), (9, 0)),
        "_말일": (L, None), "_말일결제일": (P, None),
    }


def vendors(tok):
    v = gsheet.get_values(tok, "'매입사마감'!A1:O200", sheet=DAILY)
    hi = next(i for i, r in enumerate(v) if r and r[0].strip() == "매입사명")
    out = []
    for r in v[hi + 1:]:
        if not r or not r[0].strip() or r[0].startswith("(종료)"):
            continue
        pay = r[14].strip() if len(r) > 14 else ""
        if pay in SKIP_PAY:
            continue
        out.append({"name": r[0].strip(), "kind": r[1] if len(r) > 1 else "", "pay": pay,
                    "note": r[13] if len(r) > 13 else ""})
    return out


def orders(tok, today):
    tab = f"{today.month}월_발주진행현황"
    v = gsheet.get_values(tok, f"'{tab}'!A1:Q3000", sheet=DAILY)
    hi = next(i for i, r in enumerate(v[:10]) if "업체명" in r)
    h = v[hi]
    ci = {k: h.index(k) for k in ("입고요청일", "업체명", "입고일자")}
    rows = []
    for r in v[hi + 1:]:
        if len(r) <= ci["업체명"] or not r[ci["업체명"]].strip():
            continue
        try:
            req = dt.datetime.strptime(re.sub(r"\s", "", r[ci["입고요청일"]]), "%Y.%m.%d").date()
        except (ValueError, IndexError):
            continue
        if (req.year, req.month) != (today.year, today.month):
            continue  # 지난달 탭 아래에 남은 줄 등 제외
        done = len(r) > ci["입고일자"] and r[ci["입고일자"]].strip()
        rows.append((r[ci["업체명"]].strip(), req, bool(done)))
    return rows


def key(name):
    """업체 묶음 키 — 「(제때)X」는 X와 같은 업체(요청은 한 번), 공백 무시. 두 시트 이름이 같게 관리됨(2026-11 확인)"""
    return str(name).replace(" ", "").replace("(제때)", "")


def affiliates():
    """계열사(블루푸드랩 등)는 카톡 마감 요청 대상 아님"""
    p = HERE.parents[1] / "shared" / "entities.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    return {key(a) for k, v in d.items() if not k.startswith("_") for a in [k, v.get("법인명", "")] + v.get("별칭", [])}


def mails(month_start):
    """메일로 받은 계산서·명세서 (공급자, 받은 날짜)"""
    out = []
    for f in ("pending_attach.json", "attach_resolved.json", "statements.json"):
        p = STATE / f
        if p.exists():
            for x in json.loads(p.read_text(encoding="utf-8")):
                rec = str(x.get("received", ""))[:10]
                if rec >= str(month_start + dt.timedelta(days=19)):  # 20일 이후 받은 것 = 이번 마감분으로 봄
                    out.append((x.get("supplier", ""), rec, x.get("kind", "")))
    return out


def progress_path(today):
    return STATE / f"closing_{today:%Y-%m}.json"


def load_progress(today):
    p = progress_path(today)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def build(today):
    tok = gsheet.token()
    vs, os_, ms = vendors(tok), orders(tok, today), mails(today.replace(day=1))
    L = month_end(today)
    prog = load_progress(today)
    skip = affiliates() | {"제때"}
    groups = {}
    for v in vs:  # 직납 줄이 결제조건 원본, (제때) 줄은 묶기만
        g = groups.setdefault(key(v["name"]), {**v, "name": v["name"].replace("(제때)", ""), "줄": []})
        g["줄"].append(v["name"])
        if not v["name"].startswith("(제때)"):
            g.update(pay=v["pay"], kind=v["kind"], note=v["note"])
    table = []
    for k, v in groups.items():
        if k in skip:
            continue
        mine = [(o, req, done) for o, req, done in os_ if key(o) == k]
        if not mine:
            continue  # 당월 입고 없음 → 마감 요청 안 함
        got = [(s, d, kd) for s, d, kd in ms if k and (k in key(s) or key(s) in k) and key(s)]
        table.append({
            **v,
            "입고건수": len(mine),
            "남은입고": sorted({str(req) for _, req, done in mine if req > today and not done}),
            "말일입고": any(req == L for _, req, _ in mine),
            "입고종료": all(done or req < today for _, req, done in mine),  # 오늘 입고 예정은 아직 안 끝난 것
            "말일결제": v["pay"].replace(" ", "") == "당월말일",
            "메일수신": [f"{d} {kd}" for _, d, kd in got],
            "진행": prog.get(v["name"], {}),
        })
    return table


def targets(phase, today):
    t = build(today)
    def need_request(x):
        return not x["진행"].get("요청") and not x["메일수신"]
    if phase == "payday":
        return [x for x in t if need_request(x) and x["말일결제"]]
    if phase == "early":
        return [x for x in t if need_request(x) and (x["말일결제"] or x["입고종료"])]
    if phase == "all":
        return [x for x in t if need_request(x) and not x["말일입고"]]
    if phase == "lastday":
        return [x for x in t if need_request(x) and x["말일입고"]]
    if phase == "deadline":
        return [x for x in t if x["말일결제"] and not x["진행"].get("계산서") and not any("국세청" in m or "대행사" in m for m in x["메일수신"])]
    if phase == "followup":
        return [x for x in t if x["진행"].get("요청") and not x["진행"].get("계산서")]
    raise SystemExit(f"모르는 단계: {phase}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "targets", "mark", "status"])
    ap.add_argument("args", nargs="*", help="targets: payday/early/all/lastday/deadline/followup")
    ap.add_argument("--date", help="기준일 YYYY-MM-DD (시험용)")
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    if a.cmd == "plan":
        for k, (d, hm) in plan(today).items():
            print(f"{k:10} {d} {'%02d:%02d' % hm if hm else ''}")
    elif a.cmd == "targets":
        rows = targets(a.args[0], today)
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        print(f"STATUS: {a.args[0]} 대상 {len(rows)}곳 — " + ", ".join(x["name"] for x in rows))
    elif a.cmd == "mark":
        name, key, val = a.args[0], a.args[1], " ".join(a.args[2:])
        prog = load_progress(today)
        prog.setdefault(name, {})[key] = val
        progress_path(today).write_text(json.dumps(prog, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"기록: {name} · {key} = {val}")
    elif a.cmd == "status":
        for x in build(today):
            p = x["진행"]
            print(f"{x['name']:16} 결제:{x['pay'] or '-':10} 입고{x['입고건수']}건 남은:{','.join(x['남은입고']) or '-':12} "
                  f"메일:{len(x['메일수신'])} 요청:{p.get('요청', '-')} 원장:{p.get('원장', '-')} 계산서요청:{p.get('계산서요청', '-')} 계산서:{p.get('계산서', '-')}")


if __name__ == "__main__":
    main()
