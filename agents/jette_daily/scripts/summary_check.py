# 매일 아침: DAILY 시트 「종합현황」 점검 → 특이사항만 슬랙 (읽기 전용, 2026-11-05 사용자 지시)
# 실행: python -X utf8 summary_check.py            (봇이 월~금 08:20 실행 — 08:10 재고·매출 갱신이 끝난 뒤)
#       python -X utf8 summary_check.py --full     (상단 합산 품목 코드별 전체 표, 특이사항 아닌 것까지)
#
# 보는 것 (사용자 기준, 업무노트 2026-11-05)
#  1. 「발주확인」인데 입고예정 없음 → 매입처 「(제때)…」면 제때 발주 요청, 아니면 본사(구매팀) 발주
#  2. 상단 합산 품목(5~12행) 코드별 소진 — 임박 = 다음 입고 전 소진 또는 입고예정 없이 7영업일 이내(쌀 3), 영업일 월~토.
#     같은 브랜드 S·C 등은 합계 일평균으로 출고 중 코드 → 다음 코드 순서, 브랜드가 섞이면 코드별 각자 일평균
#  3. 판단을 틀리게 만드는 수식·데이터 문제 (코드 공백, 품목리스트 미등록, 상단 합계 품목명 불일치, 범위 밖 행, 월 탭)
#  4. 새로 생긴 수식 오류 — 원래 있던 「보기에만 오류」(AV·AW #REF!, AI~AT #DIV/0!, Z~AB #N/A)는 건수 변화만
# 이미 보고한 문제는 다음 날부터 「계속」 한 줄로 줄인다 (state/summary_check.json 에 첫 발견일)
# 종합현황은 팀장님 관리 양식 — 이 스크립트는 읽기만 한다

import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
import gsheet  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
STATE = HERE / "state" / "summary_check.json"
LOGS = HERE / "logs"
TOP = range(4, 12)          # 상단 합산 블록 5~12행 (0부터 셈)
BENIGN = {("#REF!", "AV"), ("#REF!", "AW")} | {("#DIV/0!", c) for c in
          ("AI", "AJ", "AN", "AO", "AS", "AT")} | {("#N/A", c) for c in ("Z", "AA", "AB")}


def col(i):
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def num(x):
    return float(x.replace(",", "")) if re.match(r"^-?[\d,.]+$", x or "") else 0.0


def pdate(x):
    m = re.match(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", x or "")
    return dt.date(int(m[1]), int(m[2]), int(m[3])) if m else None


def add_bd(d, n):
    """영업일(월~토) n일 뒤"""
    n, x = int(n), d
    while n > 0:
        x += dt.timedelta(days=1)
        if x.weekday() != 6:
            n -= 1
    return x


def fmt(d):
    return f"{d.month}/{d.day}"


def q(v):
    return f"{v:,.0f}" if v >= 10 else f"{v:,.1f}".rstrip("0").rstrip(".")


def limit(name):
    return 3 if "쌀" in name else 7


def wait_daily_update(today, minutes=8):
    """오늘 08:10 재고·매출 갱신이 끝났는지 — PC를 늦게 켜면 같이 따라잡으므로 잠깐 기다림"""
    for _ in range(minutes * 2):
        logs = sorted(LOGS.glob(f"jette-daily_{today:%Y%m%d}_*.log"))
        logs = [p for p in logs if "dryrun" not in p.name]
        if logs:
            text = logs[-1].read_text(encoding="utf-8", errors="replace")
            m = re.search(r"종료 \(exit=(\d+)\)", text)
            if m:
                return m[1] == "0"
        time.sleep(30)
    return False


def runway(V, today, full=False):
    """상단 합산 품목 → [(품목 머리줄, [코드 줄], 특이 여부)]"""
    g = lambda r, c: (V[r][c].strip() if r < len(V) and c < len(V[r]) else "")
    nxt = lambda r: (pdate(g(r, 31)), num(g(r, 32))) if pdate(g(r, 31)) else (None, 0)
    out = []
    for top in TOP:
        code, name, unit = g(top, 6), g(top, 8), g(top, 9)
        pat = {"bt006": "전지 수육용"}.get(code, re.sub(r"\(계근\)", "", name))
        comps = [r for r in range(14, len(V)) if g(r, 6) and re.search(re.escape(pat), g(r, 8))]
        tot, avg = num(g(top, 19)), num(g(top, 15))
        tend = f"약 {tot / avg:.0f}영업일, {fmt(add_bd(today, tot / avg))} 소진" if avg > 0 else "최근 출고 없음"
        head = f"*{name}* ({code}) — 합계 {q(tot)}{unit} · 하루 {q(avg)} · 전체 {tend}"
        lines, flag = [], False
        if len({g(r, 3) for r in comps}) > 1:  # 브랜드 코드가 섞임 → 코드별 각자
            head += " _(브랜드별 따로)_"
            for r in sorted(comps, key=lambda r: -num(g(r, 19))):
                st, a = num(g(r, 19)), num(g(r, 15))
                if st == 0 and a == 0:
                    continue
                d, qty = nxt(r)
                warn = False
                if a > 0:
                    days, end = st / a, add_bd(today, st / a)
                    warn = bool((d and end < d) or (not d and round(days) <= limit(name)))
                    s = f"• {g(r, 6)} ({g(r, 3)}) *{q(st)}* · 하루 {q(a)} → 약 {days:.0f}영업일, {fmt(end)} 소진"
                else:
                    s = f"• {g(r, 6)} ({g(r, 3)}) *{q(st)}* · 최근 출고 없음"
                s += f" · 다음 입고 {fmt(d)} {q(qty)}" if d else " · 입고예정 없음"
                if warn:
                    s += "  ⚠️ *임박*"
                    flag = True
                if warn or full:
                    lines.append(s)
        else:
            active = [r for r in comps if num(g(r, 14)) > 0] or [r for r in comps if num(g(r, 13)) > 0]
            order = active + sorted([r for r in comps if r not in active and num(g(r, 19)) > 0],
                                    key=lambda r: -num(g(r, 19)))
            cur = today
            for i, r in enumerate(order):
                st, (d, qty) = num(g(r, 19)), nxt(r)
                tag = "출고 중" if r in active else "대기"
                sfx = re.search(r"[A-Z](?=\()", g(r, 8))
                label = f"{g(r, 6)} {sfx[0] + '코드 ' if sfx else ''}"
                mark = ""
                if avg > 0 and st > 0:
                    days = st / avg
                    end = cur = add_bd(cur, days)
                    rest = sum(num(g(x, 19)) for x in order[i + 1:])
                    s = f"• {label}*{q(st)}* ({tag}) → 약 {days:.0f}영업일, {fmt(end)} 소진"
                    if r in active and rest > 0 and round(days) <= limit(name):
                        mark = f"  🔁 *코드 전환 임박* (이후 다른 코드 {q(rest)})"
                    elif r in active and ((d and end < d and rest == 0) or (not d and round(days) <= limit(name))):
                        mark = "  ⚠️ *임박*"
                else:
                    s = f"• {label}*{q(st)}* ({tag})"
                    if r in active:
                        mark = f" → 재고 0, {fmt(d)} 입고까지 결품 ⚠️" if d else " → 재고 0, 입고예정 없음 ⚠️ *임박*"
                s += mark + (f" · 다음 입고 {fmt(d)} {q(qty)}" if d else "")
                flag = flag or bool(mark)
                if mark or full:
                    lines.append(s)
        nd = min([nxt(r)[0] for r in comps if nxt(r)[0]], default=None)
        if avg > 0:
            tdays = tot / avg
            if (nd and add_bd(today, tdays) < nd) or (not nd and round(tdays) <= limit(name)):
                lines.append(f"• ⚠️ *품목 전체 임박* — 합계로 약 {tdays:.0f}영업일"
                             + (f", 다음 입고 {fmt(nd)} 전 소진" if nd else ", 입고예정 없음"))
                flag = True
        out.append((head, lines, flag))
    return out


def checks(V, F, tabs, today):
    """판단을 틀리게 만드는 문제 → {키: 설명}"""
    g = lambda r, c: (V[r][c] if r < len(V) and c < len(V[r]) else "")
    f = lambda r, c: (str(F[r][c]) if r < len(F) and c < len(F[r]) else "")
    found = {}
    last = max((r for r in range(14, len(V)) if g(r, 6).strip()), default=14)
    for r in range(4, len(V)):
        code = g(r, 6)
        if code.strip() and code != code.strip():
            found[f"공백:{code.strip()}"] = (f"{code.strip()}({r + 1}행) 코드 앞뒤에 보이지 않는 공백 → 매출·재고 0으로 잡힘"
                                             " ▶ G열 코드 다시 입력")
        if r >= 14 and code.strip() and g(r, 8) == "#N/A":
            found[f"미등록:{code.strip()}"] = f"{code.strip()}({r + 1}행) 신_품목리스트 미등록 → 품목명 #N/A ▶ 품목리스트에 코드 추가"
    for top in TOP:
        pats = {col(c): (re.search(r'REGEXMATCH\(\$I\$\d+:\$I\$\d+,"([^"]+)"', f(top, c)) or [None, None])[1]
                for c in (10, 32, 37, 42)}
        base = pats["K"]
        bad = [k for k, v in pats.items() if v and base and v != base]
        if bad:
            found[f"상단매칭:{g(top, 6)}"] = (f"{g(top, 6)} {g(top, 8)}({top + 1}행) {'·'.join(bad)}열이 「{pats[bad[0]]}」로 합산 중"
                                             f"(K열은 「{base}」) ▶ 수식의 품목명을 「{base}」로")
        ends = {int(m) for c in (10, 19, 32) for m in re.findall(r"\$(\d+)\)?,", f(top, c)) if int(m) > 14}
        if ends and max(ends) < last + 1:
            found["상단범위"] = (f"상단 합계 범위가 {max(ends)}행까지 → {max(ends) + 1}~{last + 1}행 품목은 합계 제외"
                               f" ▶ 범위를 ${last + 30}까지 넓히기")
    m = re.search(r"'(?:\d{4}\D{0,2})?(\d{1,2})월_발주진행현황'", f(14, 32))
    if m and int(m[1]) != today.month:
        found[f"월탭:{today:%Y%m}"] = (f"입고예정(AF~AU) 수식이 아직 「{m[1]}월_발주진행현황」을 봄 → 이번 달 입고예정이 0으로 나옴"
                                       " ▶ 수식의 탭 이름을 이번 달 탭으로")
    if today.day >= 25:
        nm = today.month % 12 + 1
        if not any(re.fullmatch(rf"(?:\d{{4}}\D{{0,2}})?{nm}월_발주진행현황", t) for t in tabs):
            found[f"다음달탭:{nm}"] = f"{nm}월_발주진행현황 탭이 아직 없음 → 1일에 종합현황 입고예정 수식도 같이 바꿔야 함"
    if re.search(r'OR\(U\d+="삭예"', f(14, 24)):
        found["Y조건"] = ("Y열 제외 조건이 U열(안전재고 숫자)에서 「삭예·전용·이관·삭제」를 찾아 항상 통과 → 종료·삭제 품목에도 발주확인"
                         " ▶ 그 문구가 적히는 열로 바꾸기 (팀장님 확인 대기)")
    return found


def label(key):
    """반복 보고용 짧은 이름"""
    kind, _, what = key.partition(":")
    return {"공백": f"{what} 코드 공백", "미등록": f"{what} 품목리스트 미등록", "상단매칭": f"{what} 합산 품목명",
            "상단범위": "상단 합계 범위", "월탭": "입고예정 월 탭", "다음달탭": f"{what}월 발주진행현황 탭",
            "Y조건": "Y열 제외 조건"}.get(kind, key)


def errors(V):
    """수식 오류 칸 → ({(값, 열): 건수} 보기에만 오류, [칸] 그 밖의 오류)"""
    benign, other = {}, []
    for r, row in enumerate(V):
        for c, v in enumerate(row):
            if str(v).startswith("#") and v in ("#REF!", "#N/A", "#DIV/0!", "#VALUE!", "#ERROR!", "#NAME?"):
                if (v, col(c)) in BENIGN:
                    benign[v] = benign.get(v, 0) + 1
                elif not (r >= 14 and c == 8):  # 품목명 #N/A 는 미등록으로 따로 봄
                    other.append(f"{col(c)}{r + 1} {v}")
    return benign, other


def main():
    full = "--full" in sys.argv
    today = dt.date.today()
    if not full and not wait_daily_update(today):
        print("• 08:10 재고·매출 갱신이 아직 안 끝났거나 실패 — 종합현황 점검은 갱신 뒤 다시 돌려 주세요"
              " (#제때_재고_주간매출_시트갱신 에 「종합현황 점검해줘」)")
        print("STATUS: 확인 필요 · 점검 보류 (재고·매출 갱신 전)")
        return
    tok = gsheet.token()
    V = gsheet.get_values(tok, "'종합현황'!A1:BZ300")
    F = gsheet.get_values(tok, "'종합현황'!A1:BZ300", render="FORMULA")
    tabs = gsheet.tab_titles(tok)
    g = lambda r, c: (V[r][c].strip() if r < len(V) and c < len(V[r]) else "")

    if full:
        for head, lines, _ in runway(V, today, full=True):
            print(head)
            print("\n".join(lines))
            print()
        return

    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    seen = state.get("seen", {})
    out, n = [], 0

    # 1. 발주확인 + 입고예정 없음
    need = [r for r in range(4, len(V)) if g(r, 24) == "발주확인" and not g(r, 31)]
    if need:
        jt = [r for r in need if "(제때)" in g(r, 5)]
        hq = [r for r in need if r not in jt]
        row = lambda r: (f"   • {g(r, 8)[:24]} {g(r, 6)}" + (f" ({g(r, 3)})" if g(r, 3) else "")
                         + f" · 재고 {g(r, 19)} / 안전 {g(r, 20)}" + ("  _품목명 「종료」_" if "종료" in g(r, 8) else ""))
        out.append(f"*🔴 발주확인인데 입고예정 없음 {len(need)}건*")
        if jt:
            out += ["• *제때 발주 요청*"] + [row(r) for r in jt]
        if hq:
            out += ["• *본사 발주 확인*"] + [row(r) for r in hq]
        n += len(need)

    # 2. 상단 합산 품목 코드별 임박
    flagged = [(h, ls) for h, ls, fl in runway(V, today) if fl]
    if flagged:
        out.append("*🟠 상단 합산 품목 소진 임박*")
        for h, ls in flagged:
            out += [f"• {h}"] + [f"   {x}" for x in ls]
        n += len(flagged)

    # 3. 판단을 틀리게 만드는 문제 — 새로 생긴 것만 자세히, 계속되는 건 한 줄
    found = checks(V, F, tabs, today)
    new = {k: v for k, v in found.items() if k not in seen}
    old = {k: v for k, v in found.items() if k in seen}
    if new:
        out.append("*🟡 시트 문제 — 새로 발견*")
        out += [f"• {v}" for v in new.values()]
        n += len(new)
    since = lambda k: "{}/{}~".format(*map(int, seen[k][5:].split("-")))
    if old:
        out.append(f"• 미해결 {len(old)}건 (계속): " + " / ".join(f"{label(k)} {since(k)}" for k in old))
    fixed = [k for k in seen if k not in found]
    if fixed:
        out.append(f"• ✅ 해결됨: {', '.join(label(k) for k in fixed)}")

    # 4. 수식 오류 변화
    benign, other = errors(V)
    prev_other = set(state.get("other", []))
    new_err = [e for e in other if e not in prev_other]
    if new_err:
        out.append(f"*🟡 새 수식 오류 {len(new_err)}칸*")
        out.append("• " + ", ".join(new_err[:20]) + (" …" if len(new_err) > 20 else ""))
        n += 1
    prev_b = state.get("benign", {})
    if prev_b and benign != prev_b:
        out.append("• 보기에만 오류 건수 변화: " + ", ".join(f"{k} {prev_b.get(k, 0)}→{v}" for k, v in benign.items()))

    state = {"date": str(today), "seen": {k: seen.get(k, str(today)) for k in found},
             "other": other, "benign": benign}
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n".join(out) if out else "• 특이사항 없음")
    print(f"STATUS: {'확인 필요 · 특이사항 ' + str(n) + '건' if n else '특이사항 없음'}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
