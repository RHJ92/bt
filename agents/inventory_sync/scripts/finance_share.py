# 재무팀 공유용 「재고자산 명세」 파일 — 통합_재고관리 원본은 메일 초대자만, 재무팀은 이 파일 링크로 보기만 (2026-11-05 사용자 지시)
# 구글 시트는 탭별로 링크 공유를 막을 수 없어 파일을 나눴다. 이 파일은 원본 「재무팀 재고자산 명세」를 IMPORTRANGE 로 실시간 연결
# 실행: python -X utf8 finance_share.py create   (한 번만 — 새 파일 생성, ID 를 state/finance_share.json 에)
#       python -X utf8 finance_share.py months   (마감월 필터 보기 추가 — 월 마감 때마다. 원본에 새 달 행이 생기면 그 달 필터 보기를 만든다)
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
import gsheet  # noqa: E402

SRC = "1DfGgHvHuecTGySam_TiNusUtohKFwGB4AtYG_8K_ErQ"  # 통합_재고관리(로트기반)
SRC_TAB = "재무팀 재고자산 명세"
STATE = Path(__file__).resolve().parents[1] / "state" / "finance_share.json"
API = "https://sheets.googleapis.com/v4/spreadsheets"
HEAD, FIRST, LAST = 15, 16, 15 + 1696  # 명세 머리글 행 / 첫 데이터 행 / 끝 행 (원본 A11:N1706 = 1696행)


def call(method, url, tok, **kw):
    r = requests.request(method, url, headers={"Authorization": "Bearer " + tok}, timeout=120, **kw)
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.text[:500]}")
    return r.json()


def create():
    tok = gsheet.token(rw=True)
    body = {"properties": {"title": "재무팀 재고자산 명세 (통합_재고관리 연동 · 보기 전용)", "locale": "ko_KR",
                           "timeZone": "Asia/Seoul"},
            "sheets": [{"properties": {"title": "재고자산 명세", "gridProperties": {"rowCount": LAST + 5, "columnCount": 19,
                                                                              "frozenRowCount": HEAD}}}]}
    ss = call("POST", API, tok, json=body)
    sid, gid = ss["spreadsheetId"], ss["sheets"][0]["properties"]["sheetId"]
    imp = lambda rng: f'=IMPORTRANGE("{SRC}","\'{SRC_TAB}\'!{rng}")'
    values = [
        ["재고자산 명세 — 사업자별 · 마감월별 (재무팀 보기용)"],
        ["통합_재고관리(로트기반) 「재무팀 재고자산 명세」와 실시간 연결된 보기 전용 파일입니다.  마감월은 상단 메뉴 [데이터 → 필터 보기]에서"
         " 「2026-10」처럼 골라 보세요.  15행 위 「보이는 행 합계」는 고른 마감월만 더합니다.  금액은 공급가액, VAT 포함은 M열."],
        [],
        ["마감월별 합계 추이 (공급가액)"],
        [imp("P4:AH10")],
    ]
    call("PUT", f"{API}/{sid}/values/'재고자산 명세'!A1?valueInputOption=USER_ENTERED", tok, json={"values": values})
    call("PUT", f"{API}/{sid}/values/'재고자산 명세'!A13?valueInputOption=USER_ENTERED", tok, json={"values": [
        ["■ 품목 명세"],
        ["보이는 행 합계 →", "", "", "", "", "", "", "", "", f"=SUBTOTAL(109,J{FIRST}:J{LAST})", "",
         f"=SUBTOTAL(109,L{FIRST}:L{LAST})", f"=SUBTOTAL(109,M{FIRST}:M{LAST})"],
        [imp("A11:N1706")]]})
    rng = lambda r0, r1, c0, c1: {"sheetId": gid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}
    num = {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}
    font = lambda size, bold=False: {"textFormat": {"fontFamily": "Malgun Gothic", "fontSize": size, "bold": bold}}
    reqs = [
        {"repeatCell": {"range": rng(0, LAST + 5, 0, 19), "cell": {"userEnteredFormat": font(9)}, "fields": "userEnteredFormat.textFormat"}},
        {"repeatCell": {"range": rng(0, 1, 0, 1), "cell": {"userEnteredFormat": font(12, True)}, "fields": "userEnteredFormat.textFormat"}},
        {"repeatCell": {"range": rng(1, 2, 0, 1), "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP", "textFormat": {"fontFamily": "Malgun Gothic", "fontSize": 9, "foregroundColor": {"red": .4, "green": .4, "blue": .4}}}},
                        "fields": "userEnteredFormat(wrapStrategy,textFormat)"}},
        {"repeatCell": {"range": rng(3, 4, 0, 1), "cell": {"userEnteredFormat": font(9, True)}, "fields": "userEnteredFormat.textFormat"}},
        {"repeatCell": {"range": rng(4, 11, 1, 19), "cell": {"userEnteredFormat": num}, "fields": "userEnteredFormat.numberFormat"}},
        {"repeatCell": {"range": rng(4, 5, 0, 19), "cell": {"userEnteredFormat": {**font(9, True), "backgroundColor": {"red": .93, "green": .93, "blue": .93}}},
                        "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
        {"repeatCell": {"range": rng(10, 11, 0, 19), "cell": {"userEnteredFormat": font(9, True)}, "fields": "userEnteredFormat.textFormat"}},
        {"repeatCell": {"range": rng(12, 13, 0, 1), "cell": {"userEnteredFormat": font(9, True)}, "fields": "userEnteredFormat.textFormat"}},
        {"repeatCell": {"range": rng(13, 14, 0, 14), "cell": {"userEnteredFormat": {**num, **font(9, True), "backgroundColor": {"red": 1, "green": .95, "blue": .8}}},
                        "fields": "userEnteredFormat(numberFormat,textFormat,backgroundColor)"}},
        {"repeatCell": {"range": rng(HEAD - 1, HEAD, 0, 14), "cell": {"userEnteredFormat": {**font(9, True), "backgroundColor": {"red": .85, "green": .9, "blue": .97},
                                                                                         "wrapStrategy": "WRAP", "verticalAlignment": "MIDDLE"}},
                        "fields": "userEnteredFormat(textFormat,backgroundColor,wrapStrategy,verticalAlignment)"}},
        {"repeatCell": {"range": rng(FIRST - 1, LAST, 9, 13), "cell": {"userEnteredFormat": num}, "fields": "userEnteredFormat.numberFormat"}},
        {"updateDimensionProperties": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": 5, "endIndex": 6},
                                       "properties": {"pixelSize": 260}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": 6, "endIndex": 7},
                                       "properties": {"pixelSize": 150}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": 9, "endIndex": 13},
                                       "properties": {"pixelSize": 105}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": 13, "endIndex": 14},
                                       "properties": {"pixelSize": 180}, "fields": "pixelSize"}},
    ]
    call("POST", f"{API}/{sid}:batchUpdate", tok, json={"requests": reqs})
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({"id": sid, "sheetId": gid}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("생성", f"https://docs.google.com/spreadsheets/d/{sid}/edit")


SRC_GID = 773054848  # 원본 「재무팀 재고자산 명세」 탭


def rebuild():
    """원본 탭을 통째로 복사(서식·병합·열 너비·요약 수식 그대로) → 다른 탭을 보는 칸만 IMPORTRANGE 로 바꿈 (2026-11-05 「완전히 똑같이」)
    같은 탭 안에서만 계산하는 요약(A3:H9)·마감월별 추이(P3:AH10)는 복사된 수식이 그대로 돈다. 다른 탭 참조 = 명세 A12:N·자가 검증 J4·J5"""
    st = json.loads(STATE.read_text(encoding="utf-8"))
    sid, old = st["id"], st["sheetId"]
    tok = gsheet.token(rw=True)
    gid = call("POST", f"{API}/{SRC}/sheets/{SRC_GID}:copyTo", tok, json={"destinationSpreadsheetId": sid})["sheetId"]
    imp = lambda rng: f'=IMPORTRANGE("{SRC}","\'{SRC_TAB}\'!{rng}")'
    call("POST", f"{API}/{sid}:batchUpdate", tok, json={"requests": [
        {"deleteSheet": {"sheetId": old}},
        {"updateSheetProperties": {"properties": {"sheetId": gid, "title": SRC_TAB, "index": 0}, "fields": "title,index"}},
        {"setDataValidation": {"range": {"sheetId": gid, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 1, "endColumnIndex": 2}}},
    ]})
    call("POST", f"{API}/{sid}/values:batchClear", tok, json={"ranges": [f"'{SRC_TAB}'!A12:N1706", f"'{SRC_TAB}'!J4:J5"]})
    call("POST", f"{API}/{sid}/values:batchUpdate", tok, json={"valueInputOption": "USER_ENTERED", "data": [
        {"range": f"'{SRC_TAB}'!B2", "values": [[imp("B2")]]},     # 마감월 — 원본 B2 를 따라감 (보기 전용이라 여기선 못 바꿈)
        {"range": f"'{SRC_TAB}'!J4", "values": [[imp("J4:J5")]]},
        {"range": f"'{SRC_TAB}'!A12", "values": [[imp("A12:N1706")]]}]})
    st["sheetId"] = gid
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print("다시 만듦 — 탭", gid)


def months():
    """원본에 있는 마감월마다 필터 보기 1개씩 (이미 있으면 건너뜀) + 「전체」"""
    st = json.loads(STATE.read_text(encoding="utf-8"))
    sid, gid = st["id"], st["sheetId"]
    tok = gsheet.token(rw=True)
    have = {fv["title"] for s in call("GET", f"{API}/{sid}?fields=sheets(filterViews(title))", tok)["sheets"]
            for fv in s.get("filterViews", [])}
    src = gsheet.get_values(gsheet.token(), f"'{SRC_TAB}'!A12:A1706", sheet=SRC)
    ms = sorted({r[0] for r in src if r and str(r[0]).startswith("20")})
    area = {"sheetId": gid, "startRowIndex": 10, "endRowIndex": 1706, "startColumnIndex": 0, "endColumnIndex": 14}
    reqs = []
    for m in ["전체"] + ms[::-1]:
        title = f"마감월 {m}"
        if title in have:
            continue
        cond = {"type": "NOT_BLANK"} if m == "전체" else {"type": "TEXT_EQ", "values": [{"userEnteredValue": m}]}
        reqs.append({"addFilterView": {"filter": {"title": title, "range": area,
                                                  "filterSpecs": [{"columnIndex": 0, "filterCriteria": {"condition": cond}}]}}})
    if reqs:
        call("POST", f"{API}/{sid}:batchUpdate", tok, json={"requests": reqs})
    print("필터 보기 추가:", [r["addFilterView"]["filter"]["title"] for r in reqs] or "없음")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"create": create, "rebuild": rebuild, "months": months}[sys.argv[1]]()
