# 국세청 보안메일 비밀번호(받는 법인 사업자번호) 저장 + 최근 메일로 열기 시험
# 실행: python "C:\Users\BLUETREND\류호정\bt\agents\expense_report\scripts\set_nts_password.py"
# 블루트렌드 → 블루푸드랩 순서로 묻는다. 숫자만 입력(하이픈 없이). 화면에 안 보이는 게 정상. 건너뛰려면 엔터

import email
import email.policy
import getpass
import sys
from pathlib import Path

import keyring

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "mail_intake"))
from ecount_imap import connect, list_folders, open_readonly  # noqa: E402
from nts_invoice import ENTITIES, KEYRING_SERVICE, entity_of, open_invoice, parse_text  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "state" / "nts_test"


def latest_mail(entity):
    im = connect()
    try:
        open_readonly(im, dict(list_folders(im))["INBOX"])
        typ, d = im.uid("search", None, "FROM", "hometaxadmin@hometax.go.kr")
        for uid in reversed(d[0].split()[-60:]):
            typ, m = im.uid("fetch", uid, "(BODY.PEEK[])")
            msg = email.message_from_bytes(m[0][1], policy=email.policy.default)
            if entity_of(str(msg["subject"])) == entity:
                att = next(msg.iter_attachments(), None)
                if att:
                    return str(msg["subject"]), att.get_content() if isinstance(att.get_content(), bytes) \
                        else att.get_content().encode("utf-8")
    finally:
        im.logout()
    return None, None


for entity in ENTITIES:
    pw = getpass.getpass(f"\n[{entity}] 사업자번호 숫자만 (건너뛰려면 엔터): ").strip().replace("-", "")
    if not pw:
        print("  건너뜀")
        continue
    keyring.set_password(KEYRING_SERVICE, entity, pw)
    subject, html = latest_mail(entity)
    if not html:
        print("  저장함 — 시험할 최근 메일이 없음")
        continue
    try:
        png = OUT / f"{entity}.png"
        date, total = parse_text(open_invoice(html, entity, png))
        print(f"  저장·열기 성공 — {subject}\n  작성일자 {date} · 합계 {total} · 캡처 {png}")
    except Exception as e:
        keyring.delete_password(KEYRING_SERVICE, entity)
        print(f"  열기 실패 — 저장한 번호를 지웠습니다. 다시 실행해 주세요.\n  {e}")

print("\n끝. 이 창은 닫아도 됩니다.")
