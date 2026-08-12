# 클로바노트 내보내기 파일 파이프라인 (run-clovanote-watch.ps1 이 호출)
#
# 서브커맨드
#   scan    <다운로드폴더> <state.json>            처리 대상 후보를 JSON 으로 출력
#   extract <원본파일> <출력txt>                    docx/txt -> UTF-8 텍스트
#   upload  <원본파일> <드라이브폴더ID>              드라이브 업로드 (성공 시 파일ID 출력)
#   mark    <state.json> <원본파일>                 처리 완료 기록
#   seed    <다운로드폴더> <state.json> [기준일시]   기존 파일을 처리완료로 시드
#
# 출력은 전부 UTF-8 로 stdout. 콘솔 인코딩 문제를 피하려고 한글 로그는 최소화한다.

import io
import json
import os
import re
import sys
from datetime import datetime

CRED = r"C:\Users\BLUETREND\.gdrive-mcp\credentials_rw.json"

# 클로바노트 내보내기 파일만 잡는다. Downloads 의 다른 docx/txt(계약서 등)는 건드리지 않는다.
PATTERNS = [
    re.compile(r"^통화 녹음 .+\.(docx|txt)$"),
    re.compile(r"^새로운 노트.*\.(docx|txt)$"),
]


def is_target(name):
    return any(p.match(name) for p in PATTERNS)


def key_of(path):
    st = os.stat(path)
    return "%s|%d" % (os.path.basename(path), st.st_size)


def load_state(p):
    if os.path.exists(p):
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"baseline": None, "processed": {}}


def save_state(p, s):
    d = os.path.dirname(p)
    if d:  # 상대 경로로 부르면 dirname 이 빈 문자열이라 makedirs 가 터진다
        os.makedirs(d, exist_ok=True)
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps(s, ensure_ascii=False, indent=2))


def cmd_scan(dl, statefile):
    s = load_state(statefile)
    base = None
    if s.get("baseline"):
        base = datetime.fromisoformat(s["baseline"])
    out = []
    for name in os.listdir(dl):
        p = os.path.join(dl, name)
        if not os.path.isfile(p) or not is_target(name):
            continue
        mt = datetime.fromtimestamp(os.path.getmtime(p))
        if base and mt <= base:
            continue
        if key_of(p) in s["processed"]:
            continue
        out.append({"path": p, "name": name, "mtime": mt.isoformat()})
    out.sort(key=lambda x: x["mtime"])
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


def cmd_extract(src, dst):
    ext = os.path.splitext(src)[1].lower()
    if ext == ".docx":
        import docx
        text = "\n".join(par.text for par in docx.Document(src).paragraphs)
    else:
        data = open(src, "rb").read()
        text = None
        for enc in ("utf-16", "utf-8-sig", "utf-8", "cp949"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            text = data.decode("utf-8", errors="replace")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with io.open(dst, "w", encoding="utf-8") as f:
        f.write(text)
    sys.stdout.write(str(len(text)))


def _drive():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    raw = json.load(open(CRED, encoding="utf-8"))
    creds = Credentials.from_authorized_user_file(CRED, raw.get("scopes"))
    return build("drive", "v3", credentials=creds)


def cmd_upload(src, folder_id):
    from googleapiclient.http import MediaFileUpload
    svc = _drive()
    meta = {"name": os.path.basename(src), "parents": [folder_id]}
    media = MediaFileUpload(src, resumable=False)
    r = svc.files().create(body=meta, media_body=media, fields="id").execute()
    sys.stdout.write(r["id"])


def cmd_mark(statefile, src):
    s = load_state(statefile)
    s["processed"][key_of(src)] = datetime.now().isoformat(timespec="seconds")
    save_state(statefile, s)
    sys.stdout.write("ok")


def cmd_seed(dl, statefile, cutoff=None):
    s = load_state(statefile)
    cut = datetime.fromisoformat(cutoff) if cutoff else datetime.now()
    s["baseline"] = cut.isoformat(timespec="seconds")
    n = 0
    for name in os.listdir(dl):
        p = os.path.join(dl, name)
        if not os.path.isfile(p) or not is_target(name):
            continue
        if datetime.fromtimestamp(os.path.getmtime(p)) <= cut:
            s["processed"][key_of(p)] = "seeded"
            n += 1
    save_state(statefile, s)
    sys.stdout.write("seeded=%d baseline=%s" % (n, s["baseline"]))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "scan":
        cmd_scan(sys.argv[2], sys.argv[3])
    elif c == "extract":
        cmd_extract(sys.argv[2], sys.argv[3])
    elif c == "upload":
        cmd_upload(sys.argv[2], sys.argv[3])
    elif c == "mark":
        cmd_mark(sys.argv[2], sys.argv[3])
    elif c == "seed":
        cmd_seed(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    else:
        sys.stderr.write("unknown command: %s" % c)
        sys.exit(2)
