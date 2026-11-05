# 2단계: 제때 발주 메일 → 「새 발주 목록」 + 발주진행현황과 대조 (시트는 읽기만)
# 실행: python -X utf8 parse_orders.py            (최근 14일)
#       python -X utf8 parse_orders.py --days 30
# 결과: ../logs/YYMMDD_HHMM_발주목록.md
# 판단 규칙 원본: ../README.md §2

import argparse
import datetime as dt
import email
import email.policy
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "shared" / "mail_intake"))
import gsheet  # noqa: E402
from ecount_imap import connect, list_folders, mark_seen, open_readonly  # noqa: E402,F401

JETTE = "jh13659@jette.co.kr"
LOGS = Path(__file__).resolve().parents[1] / "logs"
CODE = re.compile(r"^CC\d{6}$")
FLAG = {"CC411041": "10월 마감 때 jt단가 17,100 수기 고정 대상"}  # 쪽파김치, README §2


def norm_date(s):
    """'2026-10-29' · '2026. 10. 29' · datetime → date"""
    if isinstance(s, dt.datetime):
        return s.date()
    m = re.match(r"\s*(\d{4})\D+(\d{1,2})\D+(\d{1,2})", str(s or ""))
    return dt.date(*map(int, m.groups())) if m else None


def to_int(s):
    try:
        return int(float(str(s).replace(",", "").strip()))
    except ValueError:
        return None


# ---------- 메일 읽기 ----------
def parse_subject(subj):
    """→ (구분, 기준일자 YYYYMMDD, 업체) / 발주 메일 아니면 None"""
    if "발주서" not in subj:
        return None
    m = re.search(r"(\d{8})\s*\[\(주\)제때\]\s*(.+?)\s*발주서", subj)
    if not m:
        return ("확인필요", None, subj)
    if subj.strip().upper().startswith("RE"):
        kind = "삭제" if "삭제" in subj else "정정" if re.search(r"수량\s*(정정|수정)", subj) else "회신"
    else:
        kind = "신규"
    return (kind, m[1], m[2])


def body_rows(html):
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tr in soup.find_all("tr"):
        c = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if len(c) >= 7 and CODE.match(c[2]):
            rows.append({"date": norm_date(c[0]), "code": c[2], "name": re.sub(r"\s+", " ", c[3]),
                         "qty": to_int(c[6])})
    return rows


def attach_rows(part):
    wb = openpyxl.load_workbook(io.BytesIO(part.get_content()), data_only=True)
    ws = wb.active
    grid = list(ws.iter_rows(values_only=True))
    date = next((norm_date(r[0]) for r in grid[:5] if r and isinstance(r[0], dt.datetime)), None)
    return [{"date": date, "code": r[1], "qty": to_int(r[5])}
            for r in grid if r and len(r) > 5 and isinstance(r[1], str) and CODE.match(r[1].strip())]


def fetch(since):
    im = connect()
    try:
        fs = dict(list_folders(im))
        open_readonly(im, fs["INBOX"])
        typ, d = im.uid("search", None, "FROM", JETTE, "SINCE", since.strftime("%d-%b-%Y"))
        mails = []
        for uid in d[0].split():
            typ, m = im.uid("fetch", uid, "(BODY.PEEK[])")  # PEEK = 읽음 표시 안 함
            msg = email.message_from_bytes(m[0][1], policy=email.policy.default)
            subj = str(msg["subject"] or "")
            p = parse_subject(subj)
            if not p:
                continue
            html = msg.get_body(preferencelist=("html",))
            rows = body_rows(html.get_content()) if html else []
            att = []
            for part in msg.iter_attachments():
                if (part.get_filename() or "").lower().endswith(".xlsx"):
                    att += attach_rows(part)
            mails.append({"uid": uid.decode(), "when": email.utils.parsedate_to_datetime(msg["date"]).astimezone(),
                          "subject": subj, "kind": p[0], "ref": p[1], "vendor": p[2], "rows": rows, "att": att})
        return sorted(mails, key=lambda x: x["when"])
    finally:
        im.logout()


# ---------- 판단 ----------
def check_attach(m):
    """본문 표와 첨부 엑셀 교차검증 — 첨부 없으면 통과"""
    if not m["att"]:
        return None
    b = sorted((r["date"], r["code"], r["qty"]) for r in m["rows"])
    a = sorted((r["date"], r["code"], r["qty"]) for r in m["att"])
    if a == b:
        return None
    diff = sorted(set(b) ^ set(a))
    body = ", ".join(f"{c} {q}" for d, c, q in diff if (d, c, q) in set(b))
    att = ", ".join(f"{c} {q}" for d, c, q in diff if (d, c, q) in set(a))
    return f"본문 표 ≠ 첨부 엑셀 (본문 {body or '없음'} / 첨부 {att or '없음'}) — 본문 기준 입력(첨부는 수정 안 된 옛 파일인 경우가 있음)"


def actions(mails):
    """메일 순서대로 → 처리 목록. 정정·삭제 회신은 정정 후 전체 표가 오므로 원 발주와 비교"""
    orig = {}  # (업체, 기준일자) → rows
    out = []
    for m in mails:
        note = check_attach(m)
        base = {"mail": f"{m['when']:%m/%d %H:%M} {m['vendor']}", "uid": m["uid"]}
        if m["kind"] == "신규":
            orig[(m["vendor"], m["ref"])] = m["rows"]
            for r in m["rows"]:
                act = "제외" if "당면" in r["name"] else "신규"
                out.append({**base, **r, "act": act, "prev": None,
                            "note": "; ".join(filter(None, [note, FLAG.get(r["code"]),
                                                            "당면 — 입력 안 함" if act == "제외" else None]))})
        elif m["kind"] in ("정정", "삭제"):
            o = orig.get((m["vendor"], m["ref"]))
            if o is None:
                for r in m["rows"]:
                    out.append({**base, **r, "act": "확인필요", "prev": None,
                                "note": f"원 발주({m['ref']}) 메일을 조회 기간 안에서 못 찾음 — 기간을 늘려 다시"})
                continue
            new = {(r["date"], r["code"]): r for r in m["rows"]}
            old = {(r["date"], r["code"]): r for r in o}
            for k, r in old.items():
                if k not in new:
                    out.append({**base, **r, "act": "삭제", "prev": r["qty"], "qty": 0, "note": m["kind"] + " 회신"})
                elif new[k]["qty"] != r["qty"]:
                    out.append({**base, **new[k], "act": "수정", "prev": r["qty"], "note": m["kind"] + " 회신"})
            for k, r in new.items():
                if k not in old:
                    out.append({**base, **r, "act": "신규", "prev": None, "note": m["kind"] + " 회신에 추가된 줄"})
            orig[(m["vendor"], m["ref"])] = m["rows"]
        else:
            out.append({**base, "date": None, "code": "", "name": m["subject"], "qty": None, "prev": None,
                        "act": "확인필요", "note": "제목 형식을 모름"})
    return out


def expected(acts):
    """처리 후 시트에 있어야 할 상태 (입고요청일, 코드) → 수량"""
    exp = {}
    for a in acts:
        k = (a["date"], a["code"])
        if a["act"] in ("신규", "수정"):
            exp[k] = a
        elif a["act"] == "삭제":
            exp.pop(k, None)
    return exp


TAB_RE = re.compile(r"(?:(\d{4})\D{0,2})?(\d{1,2})월_발주진행현황")


def order_tabs(titles):
    """발주진행현황 탭 → {(연, 월): 탭 이름}. 「N월_…」과 연도 붙은 「2026_12월_…」「2026년 12월_…」 모두 읽음
    — 월 숫자만으로 고르면 1월 탭이 생길 때 12월을 계속 최신으로 고르므로, 12월부터 탭 이름에 연도를 붙이기로 함(2026-11-04)
    연도 없는 탭은 2026년으로 본다(2026-01~11월 탭)"""
    out = {}
    for t in titles:
        m = TAB_RE.fullmatch(t)
        if m:
            out[(int(m[1] or 2026), int(m[2]))] = t
    return out


def sheet_rows(tok, sheet=gsheet.DAILY_SHEET):
    """가장 최근 월 발주진행현황 탭의 (입고요청일, 코드) → [(행, 수량)]"""
    tabs = order_tabs(gsheet.tab_titles(tok, sheet=sheet))
    tab = tabs[max(tabs)]
    vals = gsheet.get_values(tok, f"'{tab}'!E5:L", sheet=sheet)
    got = defaultdict(list)
    for i, r in enumerate(vals, 5):
        r = r + [""] * (8 - len(r))
        d, code, qty = norm_date(r[0]), r[3].strip(), to_int(r[7])
        if d and code:
            got[(d, code)].append((i, qty))
    return tab, got


# ---------- 보고 ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args()
    since = dt.date.today() - dt.timedelta(days=a.days)

    mails = fetch(since - dt.timedelta(days=30))  # 정정 회신의 원 발주를 찾으려고 30일 더 읽음
    acts = [x for x in actions(mails) if x["uid"] in {m["uid"] for m in mails if m["when"].date() >= since}]
    exp = expected(acts)
    tab, got = sheet_rows(gsheet.token())

    lines = [f"**제때 발주 메일 → 발주진행현황 대조** (메일 {since:%m/%d}~오늘, 시트 `{tab}`, 실행 {dt.datetime.now():%Y-%m-%d %H:%M})", ""]
    n_mail = len({x['uid'] for x in acts})
    cnt = defaultdict(int)
    for x in acts:
        cnt[x["act"]] += 1
    lines.append(f"메일 {n_mail}통 → " + " · ".join(f"{k} {v}" for k, v in cnt.items()))
    lines += ["", "**① 처리 목록 (메일 기준)**", "",
              "| 메일 | 처리 | 입고요청일 | 코드 | 제품명 | 수량 | 비고 |", "|---|---|---|---|---|---|---|"]
    for x in acts:
        q = f"{x['prev']}→{x['qty']}" if x["prev"] is not None else x["qty"]
        lines.append(f"| {x['mail']} | {x['act']} | {x['date'] or ''} | {x['code']} | {x['name'][:30]} | {q} | {x['note']} |")

    ok, diff = 0, []
    for (d, code), x in sorted(exp.items(), key=lambda kv: (kv[0][0] or dt.date.min, kv[0][1])):
        rows = got.get((d, code), [])
        if len(rows) == 1 and rows[0][1] == x["qty"]:
            ok += 1
        elif not rows:
            diff.append(("시트에 없음", d, code, x["name"], x["qty"], "-"))
        elif len(rows) > 1:
            diff.append(("시트에 중복", d, code, x["name"], x["qty"], ", ".join(f"{i}행 {q}" for i, q in rows)))
        else:
            diff.append(("수량 다름", d, code, x["name"], x["qty"], f"{rows[0][0]}행 {rows[0][1]}"))
    for x in acts:  # 삭제됐는데 시트에 남은 줄
        k = (x["date"], x["code"])
        if x["act"] == "삭제" and k not in exp and got.get(k) and any(q for _, q in got[k]):
            diff.append(("삭제됐는데 시트에 수량 있음", x["date"], x["code"], x["name"], 0,
                         ", ".join(f"{i}행 {q}" for i, q in got[k])))
    lines += ["", f"**② 시트 대조** — 일치 {ok} / 차이 {len(diff)}", ""]
    if diff:
        lines += ["| 구분 | 입고요청일 | 코드 | 제품명 | 메일 수량 | 시트 |", "|---|---|---|---|---|---|"]
        lines += [f"| {k} | {d} | {c} | {n[:30]} | {q} | {s} |" for k, d, c, n, q, s in diff]

    LOGS.mkdir(exist_ok=True)
    out = LOGS / f"{dt.datetime.now():%y%m%d_%H%M}_발주목록.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:3]))
    print(f"시트 대조: 일치 {ok} / 차이 {len(diff)}")
    for k, d, c, n, q, s in diff:
        print(f"  {k} | {d} | {c} | {n[:24]} | 메일 {q} | 시트 {s}")
    print("결과:", out)


if __name__ == "__main__":
    main()
