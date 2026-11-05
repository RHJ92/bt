"""DAILY 업무 진행 시트 스냅샷 / 비교 도구 (매입마감 검토용)

사용법
  python -I sheet_snapshot.py snap <라벨>          # 지금 상태를 snapshots/<라벨>/ 에 저장
  python -I sheet_snapshot.py diff <라벨A> <라벨B>  # 두 스냅샷의 바뀐 셀 목록
  python -I sheet_snapshot.py revs                  # 드라이브 수정 이력(누가·언제)

값(FORMATTED_VALUE)과 수식(FORMULA)을 둘 다 저장한다. 수식 칸에 값을 덮어쓴 경우도 잡기 위해서.
"""
import json, sys, time, urllib.parse
from pathlib import Path
import requests

SHEET_ID = "1x1KueQVbAyKYQJV_3pkcHZhJc5YJqjSbadiCIr3tRns"
TABS = ["10월_발주진행현황", "매입사마감", "신_품목리스트", "신_단가변동사항", "중간단가변경이력", "종합현황"]
CRED_DIR = Path(r"C:\Users\BLUETREND\.gdrive-mcp")
BASE = Path(__file__).parent / "snapshots"


def token():
    keys = json.loads((CRED_DIR / "gcp-oauth.keys.json").read_text(encoding="utf-8"))
    keys = keys.get("installed") or keys.get("web")
    cred = json.loads((CRED_DIR / "credentials.json").read_text(encoding="utf-8"))
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": keys["client_id"], "client_secret": keys["client_secret"],
        "refresh_token": cred["refresh_token"], "grant_type": "refresh_token"})
    r.raise_for_status()
    return r.json()["access_token"]


def get_values(tok, tab, render):
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/"
           f"{urllib.parse.quote(tab)}?valueRenderOption={render}")
    r = requests.get(url, headers={"Authorization": f"Bearer {tok}"})
    r.raise_for_status()
    return r.json().get("values", [])


def snap(label):
    tok = token()
    out = BASE / label
    out.mkdir(parents=True, exist_ok=True)
    meta = {"taken_at": time.strftime("%Y-%m-%d %H:%M:%S"), "tabs": {}}
    for tab in TABS:
        data = {"values": get_values(tok, tab, "FORMATTED_VALUE"),
                "formulas": get_values(tok, tab, "FORMULA")}
        (out / f"{tab}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        meta["tabs"][tab] = len(data["values"])
    (out / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


def col(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def cell(grid, r, c):
    return grid[r][c] if r < len(grid) and c < len(grid[r]) else ""


def diff(a, b):
    for tab in TABS:
        pa, pb = BASE / a / f"{tab}.json", BASE / b / f"{tab}.json"
        if not (pa.exists() and pb.exists()):
            continue
        A = json.loads(pa.read_text(encoding="utf-8"))
        B = json.loads(pb.read_text(encoding="utf-8"))
        rows = max(len(A["formulas"]), len(B["formulas"]))
        changes = []
        for r in range(rows):
            cols = max(len(A["formulas"][r]) if r < len(A["formulas"]) else 0,
                       len(B["formulas"][r]) if r < len(B["formulas"]) else 0)
            for c in range(cols):
                fa, fb = cell(A["formulas"], r, c), cell(B["formulas"], r, c)
                va, vb = cell(A["values"], r, c), cell(B["values"], r, c)
                if fa != fb:
                    kind = "입력변경"
                    if str(fa).startswith("=") and not str(fb).startswith("="):
                        kind = "수식→값 덮어씀"
                    elif str(fa).startswith("=") or str(fb).startswith("="):
                        kind = "수식변경"
                    changes.append((f"{col(c)}{r+1}", kind, fa, fb, va, vb))
                elif va != vb and str(fa).startswith("="):
                    changes.append((f"{col(c)}{r+1}", "계산결과변경", "", "", va, vb))
        print(f"\n=== {tab}: {len(changes)}건")
        for ref, kind, fa, fb, va, vb in changes:
            if kind == "계산결과변경":
                print(f"  {ref}\t{kind}\t{va!r} → {vb!r}")
            else:
                print(f"  {ref}\t{kind}\t{fa!r} → {fb!r}  (표시값 {va!r} → {vb!r})")


def revs():
    tok = token()
    r = requests.get(f"https://www.googleapis.com/drive/v3/files/{SHEET_ID}/revisions",
                     params={"fields": "revisions(id,modifiedTime,lastModifyingUser/displayName)", "pageSize": 1000},
                     headers={"Authorization": f"Bearer {tok}"})
    r.raise_for_status()
    for v in r.json().get("revisions", [])[-30:]:
        print(v["modifiedTime"], v.get("lastModifyingUser", {}).get("displayName", "?"))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "snap":
        snap(sys.argv[2])
    elif cmd == "diff":
        diff(sys.argv[2], sys.argv[3])
    elif cmd == "revs":
        revs()
