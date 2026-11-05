# 유니폼 선분출 신청 시트 1회 생성 (한 번만 실행) — 영업팀 공유용, 금액 없음
# 결과 ID: ../state/preship_sheet.json

import json
import sys
from pathlib import Path

import requests

import verify_migration as vm

STATE = Path(__file__).resolve().parents[1] / "state" / "preship_sheet.json"
SOURCE = "1DfGgHvHuecTGySam_TiNusUtohKFwGB4AtYG_8K_ErQ"
HEAD = ["신청일", "신청자", "브랜드", "매장", "품목", "수량", "희망 수령일", "받는 곳", "비고",
        "상태", "분출일", "출고창고", "마켓봄 주문번호", "구매팀 메모"]
SALES_COLS = 9  # A~I 영업팀 입력, J~N 구매팀
MAX = 1000


def main():
    if STATE.exists():
        sys.exit("이미 만들어져 있음: " + STATE.read_text(encoding="utf-8"))
    t = vm.g_token(True)
    h = {"Authorization": "Bearer " + t}
    items = []
    head = None
    for r in vm.values(t, SOURCE, "MK_품목 마스터"):
        if head is None:
            if r and r[0] == "품목코드":
                head = r
            continue
        if r and any(w in str(r[0]) for w in ("유니폼", "모자")):
            items.append(str(r[0]))
    brands = ["옥된장", "석문어", "정백선"]
    body = {"properties": {"title": "유니폼 선분출 신청"},
            "sheets": [{"properties": {"title": "신청", "gridProperties": {"rowCount": MAX, "columnCount": len(HEAD), "frozenRowCount": 2}}},
                       {"properties": {"title": "사용 안내"}}]}
    s = requests.post("https://sheets.googleapis.com/v4/spreadsheets", headers=h, json=body, timeout=60)
    s.raise_for_status()
    s = s.json()
    sid = s["spreadsheetId"]
    tab = s["sheets"][0]["properties"]["sheetId"]
    guide = [["유니폼 선분출 신청 안내"], [""], ["1. 「신청」 탭 빈 줄에 A~I 칸을 입력합니다. 품목 1개당 1줄입니다."],
             ["2. 신청하면 바로 분출 대상입니다. 별도 승인은 없습니다."], ["3. 수량 수정은 「상태」가 비어 있을 때만 직접 고쳐 주세요."],
             ["4. 분출이 끝나면 구매팀이 J~N 칸을 채웁니다. 이후 변경은 구매팀에 요청해 주세요."],
             ["5. 초도 주문을 넣으실 때는 비고에 선분출 건임을 적어 주세요."]]
    requests.post(f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values:batchUpdate", headers=h, timeout=60, json={
        "valueInputOption": "RAW", "data": [
            {"range": "신청!A1", "values": [["영업팀 입력"] + [""] * (SALES_COLS - 1) + ["구매팀 입력"]]},
            {"range": "신청!A2", "values": [HEAD]}, {"range": "사용 안내!A1", "values": guide}]}).raise_for_status()
    rng = lambda c0, c1, r0=2, r1=MAX: {"sheetId": tab, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}
    dv = lambda r, vals: {"setDataValidation": {"range": r, "rule": {"condition": {
        "type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in vals]}, "showCustomUi": True, "strict": True}}}
    date = lambda r: {"setDataValidation": {"range": r, "rule": {"condition": {"type": "DATE_IS_VALID"}, "strict": True}}}
    font = {"fontFamily": "맑은 고딕", "fontSize": 9}
    reqs = [
        {"repeatCell": {"range": {"sheetId": tab}, "cell": {"userEnteredFormat": {"textFormat": font}}, "fields": "userEnteredFormat.textFormat"}},
        {"repeatCell": {"range": rng(0, SALES_COLS, 0, 2), "cell": {"userEnteredFormat": {"backgroundColor": {"red": .85, "green": .92, "blue": 1},
         "textFormat": {**font, "bold": True}}}, "fields": "userEnteredFormat(backgroundColor,textFormat)"}},
        {"repeatCell": {"range": rng(SALES_COLS, len(HEAD), 0, 2), "cell": {"userEnteredFormat": {"backgroundColor": {"red": .93, "green": .93, "blue": .93},
         "textFormat": {**font, "bold": True}}}, "fields": "userEnteredFormat(backgroundColor,textFormat)"}},
        dv(rng(2, 3), brands), dv(rng(4, 5), items), dv(rng(9, 10), ["분출완료", "취소"]), dv(rng(11, 12), ["본사창고", "경인양행"]),
        date(rng(0, 1)), date(rng(6, 7)), date(rng(10, 11)),
        {"setDataValidation": {"range": rng(5, 6), "rule": {"condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "0"}]}, "strict": True}}},
        {"repeatCell": {"range": rng(0, 1), "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}}, "fields": "userEnteredFormat.numberFormat"}},
        {"repeatCell": {"range": rng(6, 7), "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}}, "fields": "userEnteredFormat.numberFormat"}},
        {"repeatCell": {"range": rng(10, 11), "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}}, "fields": "userEnteredFormat.numberFormat"}},
        {"addProtectedRange": {"protectedRange": {"range": rng(SALES_COLS, len(HEAD)), "description": "구매팀 입력", "warningOnly": False,
                                                  "editors": {"users": ["yy1005.rhj@gmail.com"]}}}},
        {"addProtectedRange": {"protectedRange": {"range": rng(0, len(HEAD), 0, 2), "description": "머리글", "warningOnly": False,
                                                  "editors": {"users": ["yy1005.rhj@gmail.com"]}}}},
    ]
    for i, w in enumerate((90, 70, 70, 150, 190, 55, 90, 150, 200, 75, 90, 80, 150, 180)):
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": tab, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                                   "properties": {"pixelSize": w}, "fields": "pixelSize"}})
    requests.post(f"https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate", headers=h, json={"requests": reqs}, timeout=60).raise_for_status()
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({"id": sid}), encoding="utf-8")
    print("품목", len(items), items[:6])
    print(f"https://docs.google.com/spreadsheets/d/{sid}/edit")


if __name__ == "__main__":
    main()
