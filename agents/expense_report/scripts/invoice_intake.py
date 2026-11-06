# 계산서 메일 수집: 이카운트 메일함 → 국세청 보안메일 열어 PNG 저장 → 「노션 첨부 대기」 목록 + 슬랙 알림
# 실행: python -X utf8 invoice_intake.py            (등록된 모든 이카운트 계정, 처리 안 한 최근 14일 메일)
#       python -X utf8 invoice_intake.py --days 30
# 노션 「확인용」 카드 첨부는 이 스크립트가 하지 않음 — 목록(state/pending_attach.json)을 보고 Claude가 크롬으로 (README §7)
# 메일함은 읽기 전용, 처리한 메일은 state/invoices.json 에 UID 기록

import argparse
import datetime as dt
import email
import email.policy
import email.utils
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared" / "mail_intake"))
sys.path.insert(0, str(ROOT / "shared" / "slack_bot"))
import keyring  # noqa: E402
from ecount_imap import KEYRING_SERVICE, accounts, connect, list_folders, mark_seen, open_readonly  # noqa: E402
from notify import send  # noqa: E402
from agency_invoice import open_agency, parse_agency, site_of  # noqa: E402
from nts_invoice import entity_of, open_invoice, parse_text, supplier_of  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
STATE = HERE / "state"
DONE = STATE / "invoices.json"
PENDING = STATE / "pending_attach.json"
# 대행사가 계산서와 같이 보내는 「전자거래명세표」 메일(PDF 첨부) — 계산서와 짝지을 때까지 여기 보관 (2026-11-04 사용자 요청, 좋은에프앤비)
STATEMENTS = STATE / "statements.json"
PAIR_DAYS = 14  # 명세표 ↔ 계산서 수신일 차이 허용
SAVE_DIR = Path.home() / "Desktop" / "지출결의 증빙 이미지" / "계산서_수신"
NTS = "hometaxadmin@hometax.go.kr"
# 발행 대행사 메일: 보낸사람 주소 일부 → 제목에서 공급자 뽑는 규칙
ASP = {
    "safebill.co.kr": r"거래처:(.+?)/",
    "popbill.com": r"\[(.+?)\]",
    "logisbill.com": r"^(?:\"?)(.+?)\s+(?:세금)?계산서",
    "logisbill.co": r"^(?:\"?)(.+?)\s+(?:세금)?계산서",
    "businesson.co": r"\]\s*(.+?)\s*▶",
    "smileedi.com": r"^(.+?)에서",
    "magicbill": r"^(.+?)에서",
    "ecount.com": r"^\[?(.+?)\]?\s*\(으\)로부터",
    "bill36524.com": r"\[(.+?)\s*님\]",  # 위하고(더존)
}


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path, data):
    STATE.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def asp_info(sender, subject):
    for key, pat in ASP.items():
        if key in sender:
            m = re.search(pat, subject)
            amt = re.search(r"공급가:([\d,]+)", subject)
            return (m[1].strip() if m else subject[:30]), (int(amt[1].replace(",", "")) if amt else None)
    return None


def _entities():
    p = Path(__file__).resolve().parents[2] / "shared" / "entities.json"
    return {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args()
    since = dt.date.today() - dt.timedelta(days=a.days)
    done, pending = set(load(DONE, [])), load(PENDING, [])

    new = []
    for alias, acc in accounts().items():
        if alias == "개인":
            continue  # 담당자 개인 메일은 발송용 — 계산서 수집 대상 아님
        if not keyring.get_password(KEYRING_SERVICE, acc["user"]):
            continue  # 비밀번호 미등록 계정은 건너뜀
        try:
            im = connect(alias)
        except Exception as e:
            new.append({"uid": f"{alias}:-", "kind": "오류", "supplier": alias, "note": f"메일 접속 실패 — {e}"})
            continue
        try:
            new += scan(im, alias, since, done)
        finally:
            im.logout()
    stmts_new = [x for x in new if x["kind"] == "명세서"]
    sales_new = [x for x in new if x["kind"] == "매출"]  # 역발행 요청 = 우리가 발행하는 매출 건 → 첨부 대기 아님
    new = [x for x in new if x["kind"] != "명세서"]
    new_ok = [x for x in new if x["kind"] not in ("오류", "매출")]
    # 구매팀이 지결하지 않는 사업장(entities.json 「구매팀지결」: false, 예: 반값한근보쌈 = 김민혁 팀장 진행, 2026-11-06)
    # → PNG는 저장하되 첨부 대기에 넣지 않고, 웹메일 「읽음」도 하지 않음(담당자가 직접 보게)
    others = {k for k, v in _entities().items() if v.get("구매팀지결") is False}
    skipped = [x for x in new_ok if x.get("entity") in others]
    new_ok = [x for x in new_ok if x.get("entity") not in others]
    for x in skipped:
        print(f"구매팀 지결 아님(첨부 대기 제외): {x.get('supplier')} → {x.get('entity')} {x.get('total') or ''}")

    pending += new_ok
    stmts = load(STATEMENTS, []) + stmts_new
    paired = pair(pending, stmts)
    save(PENDING, pending)
    save(STATEMENTS, stmts)
    save(DONE, sorted(done | {x["uid"] for x in new_ok + stmts_new + skipped + sales_new}))
    new_ok += stmts_new  # 읽음 표시 대상
    # 수집 끝난 계산서 메일은 웹메일에서 「읽음」으로 — 계정별로 (열기 실패 등 확인 필요 건은 안 읽음으로 남김)
    by_acc = {}
    for x in new_ok:
        if not (x.get("note") and x["kind"] == "국세청"):
            acc, uid = x["uid"].split(":", 1)
            by_acc.setdefault(acc, []).append(uid)
    for acc, uids in by_acc.items():
        try:
            mark_seen(uids, acc)
        except Exception as e:
            print(f"({acc} 읽음 표시 실패: {e})")

    lines = [f"🧾 *계산서 메일 {len(new_ok) - len(stmts_new)}건 수신* (노션 첨부 대기 누적 {len(pending)}건)"]
    for x in new:
        amt = f" · {x['total']:,}원" if x.get("total") else ""
        lines.append(f"• [{x.get('account', '')}] {x['supplier']}{amt} ({x['kind']}"
                     f"{', ' + x['entity'] if x.get('entity') else ''})"
                     + (" 📄 거래명세표 있음" if x.get("statement") else "")
                     + (f" ⚠️ {x['note']}" if x.get("note") and x["kind"] != "대행사" else ""))
    for x in stmts_new:
        lines.append(f"• [{x.get('account', '')}] {x['supplier']} 거래명세표"
                     + (" → 계산서와 짝지음" if x["uid"] in paired else " (계산서 아직 — 오면 짝지음)"))
    for p in pending:  # 지난번에 온 계산서에 이번에 명세표가 붙은 경우
        if p not in new and any(s["uid"] in paired for s in p.get("statement", []) if isinstance(s, dict)):
            lines.append(f"• {p['supplier']} 계산서(지난 수신)에 거래명세표 짝지음")
    if new or stmts_new:
        lines.append("→ #업무지시 에 「계산서 첨부해줘」라고 쓰면 노션 카드 확인 후 없는 것만 첨부해요")
        warn = any(x.get("note") and x["kind"] != "대행사" for x in new)
        send("invoice", "\n".join(lines), "warn" if warn else "ok")
    print("\n".join(lines))
    names = ", ".join(dict.fromkeys(re.sub(r"주식회사|\(주\)|㈜", "", x.get("supplier") or "?").strip()
                                    for x in pending))  # 현황판에 업체명까지 (2026-10-30 사용자 요청)
    print(f"STATUS: 완료 · 새 계산서 {len(new_ok) - len(stmts_new)}건"
          + (f" · 거래명세표 {len(stmts_new)}건" if stmts_new else "") + f" · 첨부 대기 {len(pending)}건" + (f"({names})" if names else ""))


def _name(s):
    return re.sub(r"주식회사|유한회사|\(주\)|㈜|\(유\)|\s", "", s or "")


def _when(x):
    return dt.datetime.strptime(x["received"], "%Y-%m-%d %H:%M")


def pair(pending, stmts):
    """아직 짝 없는 거래명세표를 같은 공급자·수신일 14일 안의 계산서(첨부 대기)에 붙임 → 이번에 짝지은 명세표 uid"""
    paired = set()
    for s in stmts:
        if s.get("paired_to"):
            continue
        cands = [p for p in pending if _name(p.get("supplier")) == _name(s["supplier"])
                 and abs((_when(p) - _when(s)).days) <= PAIR_DAYS]
        if not cands:
            continue
        p = min(cands, key=lambda p: abs(_when(p) - _when(s)))
        p.setdefault("statement", []).append({k: s[k] for k in ("uid", "received", "pdf", "png") if s.get(k)})
        s["paired_to"] = p["uid"]
        paired.add(s["uid"])
    cut = dt.datetime.now() - dt.timedelta(days=60)
    stmts[:] = [s for s in stmts if _when(s) > cut]
    return paired


def save_statement(msg, item, when, u, sender, alias):
    """거래명세표 PDF 첨부 저장 + 첫 장 PNG (승인 카드·노션 첨부용). PDF 없이 링크만 오는 곳(이카운트)은 링크를 열어 캡처"""
    base = SAVE_DIR / f"{when:%y%m%d}_{re.sub(r'[\\/:*?<>|]', '', item['supplier'])}_거래명세표_{u.replace(':', '_')}"
    att = next((p for p in msg.iter_attachments() if (p.get_filename() or "").lower().endswith(".pdf")), None)
    if att is None:
        body = msg.get_body(preferencelist=("html", "plain"))
        try:
            item["total"] = parse_agency(open_agency(sender, body.get_content() if body else "", alias,
                                                     base.with_suffix(".png")))[1]
            item["png"] = str(base.with_suffix(".png"))
        except Exception as e:
            item["note"] = f"거래명세표 PDF 첨부 없음·링크 열기 실패 — 확인 필요 ({e})"
        return
    pdf = base.with_suffix(".pdf")
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(att.get_content())
    item["pdf"] = str(pdf)
    try:
        import fitz
        with fitz.open(pdf) as doc:
            doc[0].get_pixmap(dpi=150).save(str(base.with_suffix(".png")))
        item["png"] = str(base.with_suffix(".png"))
    except Exception as e:
        item["note"] = f"PNG 변환 실패 — PDF로 확인 ({e})"


def scan(im, alias, since, done):
    """한 계정 받은메일함에서 처리 안 한 계산서 메일 → 항목 목록"""
    new = []
    open_readonly(im, dict(list_folders(im))["INBOX"])
    typ, d = im.uid("search", None, "SINCE", since.strftime("%d-%b-%Y"))
    for uid in d[0].split():
        u = f"{alias}:{uid.decode()}"
        if u in done:
            continue
        typ, h = im.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        hdr = email.message_from_bytes(h[0][1], policy=email.policy.default)
        sender, subject = str(hdr["from"]), str(hdr["subject"] or "")
        when = email.utils.parsedate_to_datetime(hdr["date"]).astimezone()
        item = {"uid": u, "received": f"{when:%Y-%m-%d %H:%M}", "subject": subject}
        if NTS in sender:
            entity = entity_of(subject)
            item.update(kind="국세청", supplier=supplier_of(subject), entity=entity)
            if entity is None:
                item["note"] = "받는 법인을 모름 — 확인 필요"
            else:
                typ, m = im.uid("fetch", uid, "(BODY.PEEK[])")
                msg = email.message_from_bytes(m[0][1], policy=email.policy.default)
                att = next((p for p in msg.iter_attachments()
                            if (p.get_filename() or "").lower().endswith(".html")), None)
                if att is None:
                    item["note"] = "첨부 없음 — 확인 필요"
                else:
                    c = att.get_content()
                    png = SAVE_DIR / f"{when:%y%m%d}_{re.sub(r'[\\/:*?<>|]', '', item['supplier'])}_{u.replace(':', '_')}.png"
                    try:
                        date, total = parse_text(open_invoice(c if isinstance(c, bytes) else c.encode("utf-8"),
                                                              entity, png))
                        item.update(png=str(png), issued=date, total=total)
                    except Exception as e:
                        item["note"] = f"보안메일 열기 실패 — {e}"
        elif "역발행" in subject and (info := asp_info(sender, subject)):
            # 「[업체]에서 전자세금계산서 역발행 요청이 되었습니다」 = 우리가 **공급자**인 매출 건 (2026-11-06 넥스트키친)
            # 제목의 [업체명]은 공급받는자다(ASP 정규식은 정발행 기준이라 뒤바뀐다). 지결·첨부 대상이 아니므로
            # 조회 화면을 열지 않고(승인 버튼이 있는 화면이다) 금액만 본문에서 읽어 알린다
            item.update(kind="매출", supplier=info[0],
                        note="역발행 요청 — 우리가 공급자로 발행해야 하는 매출 건(지결 대상 아님). 제목의 업체명은 공급받는자")
            try:
                typ, m = im.uid("fetch", uid, "(BODY.PEEK[])")
                msg = email.message_from_bytes(m[0][1], policy=email.policy.default)
                body = msg.get_body(preferencelist=("html", "plain"))
                txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body.get_content() if body else ""))
                sup = re.search(r"공급자 정보 상호 ([^ ]+(?: [^ ]+)*?) 담당자", txt)
                sv = re.search(r"공급가액 ([\d,]+) 원", txt)
                tv = re.search(r"세액 ([\d,]+) 원", txt)
                dv = re.search(r"작성일자 (\d{4}-\d{2}-\d{2})", txt)
                if sv:
                    item["total"] = int(sv[1].replace(",", "")) + (int(tv[1].replace(",", "")) if tv else 0)
                if dv:
                    item["issued"] = dv[1]
                if sup:
                    item["note"] += f" / 공급자(=우리) {sup[1]} → 공급받는자 {info[0]}"
            except Exception as e:
                item["note"] += f" / 본문 읽기 실패 — {e}"
        elif "계산서" in subject and (info := asp_info(sender, subject)):
            item.update(kind="대행사", supplier=info[0], total=info[1],
                        note="대행사 메일 — 원본은 메일 본문 링크(로그인 필요할 수 있음)")
            if site_of(sender):  # 여는 방법이 검증된 대행사는 사업자번호로 열어 PNG 저장 (agency_invoice.py)
                typ, m = im.uid("fetch", uid, "(BODY.PEEK[])")
                msg = email.message_from_bytes(m[0][1], policy=email.policy.default)
                body = msg.get_body(preferencelist=("html", "plain"))
                png = SAVE_DIR / f"{when:%y%m%d}_{re.sub(r'[\\/:*?<>|]', '', item['supplier'])}_{u.replace(':', '_')}.png"
                try:
                    date, total = parse_agency(open_agency(sender, body.get_content() if body else "", alias, png))
                    item.update(png=str(png), issued=date, total=total, note=None)
                except Exception as e:
                    item["note"] = f"대행사 계산서 열기 실패 — {e}"
        elif "거래명세" in subject and (m := re.search(r"^\"?(.+?)\"?\s*에서\s*발행한", subject)
                                        or (asp_info(sender, subject) or [None])[0]):
            item.update(kind="명세서", supplier=m[1].strip() if isinstance(m, re.Match) else m)
            typ, raw = im.uid("fetch", uid, "(BODY.PEEK[])")
            save_statement(email.message_from_bytes(raw[0][1], policy=email.policy.default), item, when, u, sender, alias)
        else:
            continue
        item["account"] = alias
        new.append(item)
    return new


if __name__ == "__main__":
    main()
