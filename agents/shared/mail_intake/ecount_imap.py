# 이카운트 웹메일 IMAP 공용 함수 — 업무 폴더가 가져다 쓴다
# 서버 정보: 각 계정 웹메일 상단 「외부연동가이드」 → 서버 정보설정 (계정마다 wmbox1~4 중 하나)
# 전제: 계정마다 웹메일 프로필 → 개인기능설정 → 외부연동설정 → [메일 클라이언트 사용] = 사용
# 계정 목록: ../config/ecount_accounts.json {"별칭": {"user": 주소, "host": 서버}} (깃 미추적, set_password.py 가 기록)
# 비밀번호: Windows 자격 증명 관리자 "ecount-imap" / 사용자명 = 메일 주소
# 원칙: 메일함은 읽기 전용으로 연다(EXAMINE + BODY.PEEK). 처리가 끝난 메일만 mark_seen()으로 「읽음」 표시
#       (2026-10-29 사용자 요청 — 웹메일에서 확인한 것처럼 보이게). 이동·삭제는 안 함.
#       처리 여부 판단은 여전히 각 업무 폴더 state/ 의 UID 기록

import base64
import imaplib
import json
from pathlib import Path

import keyring

PORT = 993
KEYRING_SERVICE = "ecount-imap"
ACCOUNTS_FILE = Path(__file__).resolve().parents[1] / "config" / "ecount_accounts.json"
DEFAULT_ALIAS = "발주서수신"
# 첫 계정(2026-10-29 등록) — 설정 파일이 없을 때의 기본값
_DEFAULT = {DEFAULT_ALIAS: {"user": "invoice@bluetrend.co.kr", "host": "wmbox3.ecount.com"}}
HOST, USER = _DEFAULT[DEFAULT_ALIAS]["host"], _DEFAULT[DEFAULT_ALIAS]["user"]


def accounts():
    acc = dict(_DEFAULT)
    if ACCOUNTS_FILE.exists():
        acc.update(json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8")))
    return acc


def save_account(alias, user, host):
    acc = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8")) if ACCOUNTS_FILE.exists() else {}
    acc[alias] = {"user": user, "host": host}
    ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_FILE.write_text(json.dumps(acc, ensure_ascii=False, indent=1), encoding="utf-8")


def login(user, host, password):
    imap = imaplib.IMAP4_SSL(host, PORT)
    imap.login(user, password)
    return imap


def connect(alias=DEFAULT_ALIAS):
    a = accounts()[alias]
    pw = keyring.get_password(KEYRING_SERVICE, a["user"])
    if not pw:
        raise RuntimeError(f"{alias}({a['user']}) 비밀번호가 저장돼 있지 않음 — set_password.py 먼저 실행")
    return login(a["user"], a["host"], pw)


def decode_folder(name):
    """IMAP 수정 UTF-7 폴더명(&ycDGtA- 등) → 한글"""
    out, i = [], 0
    while i < len(name):
        if name[i] == "&":
            j = name.index("-", i)
            if j == i + 1:
                out.append("&")
            else:
                b64 = name[i + 1:j].replace(",", "/")
                b64 += "=" * (-len(b64) % 4)
                out.append(base64.b64decode(b64).decode("utf-16-be"))
            i = j + 1
        else:
            out.append(name[i])
            i += 1
    return "".join(out)


def list_folders(imap):
    """[(한글 폴더명, 원래 폴더명)]"""
    typ, rows = imap.list()
    folders = []
    for row in rows:
        raw = row.decode()
        # 형식: (\HasNoChildren) "/" "INBOX/&ycDGtA-"
        name = raw.rsplit(' "', 1)[-1].rstrip('"') if raw.endswith('"') else raw.rsplit(" ", 1)[-1]
        folders.append((decode_folder(name), name))
    return folders


def mark_seen(uids, alias=DEFAULT_ALIAS, folder="INBOX"):
    """처리 끝난 메일을 「읽음」으로 표시 (웹메일 초록색 사라짐). 이동·삭제는 하지 않음 — 2026-10-29 사용자 요청"""
    uids = [str(u) for u in uids if str(u).isdigit()]
    if not uids:
        return 0
    imap = connect(alias)
    try:
        raw = dict(list_folders(imap))[folder]
        imap.select(f'"{raw}"')  # 읽기·쓰기 모드 — 플래그 변경만
        for i in range(0, len(uids), 200):
            imap.uid("store", ",".join(uids[i:i + 200]), "+FLAGS", r"(\Seen)")
        return len(uids)
    finally:
        imap.logout()


def open_readonly(imap, raw_folder):
    """폴더를 읽기 전용으로 선택, 메일 수 반환"""
    typ, data = imap.select(f'"{raw_folder}"', readonly=True)
    if typ != "OK":
        raise RuntimeError(f"폴더 열기 실패: {raw_folder} {data}")
    return int(data[0])
