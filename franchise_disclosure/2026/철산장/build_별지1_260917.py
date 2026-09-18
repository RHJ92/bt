"""철산장 정보공개서 별지1 작성 — 2026년 9월 통합 품목리스트 기준.

입력: 2026년도 9월 기준 통합 품목리스트.xlsx, received/ 원본 양식
출력: output/ 작성본(양식 유지) + 대사표
마진율 = 통합리스트 W열(총마진율) = (공급단가 − BT매입단가) ÷ 공급단가 — 전년 양식 기재값과 같은 기준
"""
import re
from copy import copy
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

HERE = Path(__file__).parent
LIST = HERE / "2026년도 9월 기준 통합 품목리스트.xlsx"
FORM = HERE / "received" / "4.가맹점 개설 견적 요청서_철산장_202610.xlsx"
OUT_FORM = HERE / "output" / "4.가맹점 개설 견적 요청서_철산장_202610_260917.xlsx"
OUT_CHECK = HERE / "output" / "철산장_별지1_대사표_리스트기준_260917.xlsx"

RED = "FFFF0000"
MEMO_FILL = PatternFill("solid", fgColor="FFFCE4D6")

L = openpyxl.load_workbook(LIST, data_only=True).active


def item(row):
    r = [c.value for c in L[row]]
    return dict(row=row, 강제=r[2], 구분=r[3], 브랜드=r[5], 품명=r[8], 과세=r[12],
                BT매입=r[13], 제때구매=r[16], 공급단가=r[19], 공급가=r[21], 마진율=r[22],
                제때=r[23], 본사=r[24], BT=r[26], 매입사=r[33])


def pct(w):
    return f"{round(w * 100, 1):g}%"


def 기준문구(it):
    if it["구분"] == "전용":
        return f"공급가격은 가맹본부가 결정하며, 가맹본부는 가맹점사업자에 대한 공급가격의 {pct(it['마진율'])}를 경제적 이익으로 수취"
    # 범용: 제때 직매입, BT 마진 없음. 가맹본부 판매장려금 약 5%(memo/BT_운영구조.md) — 기재 여부 팀장 확인 필요
    return "공급가격은 (주)제때가 결정하며, 가맹본부는 (주)제때로부터 공급가격의 약 5%를 판매장려금으로 수취"


# ── 시트1 초도물품(강제) : 양식 행 → 통합리스트 행
S1 = {17: 39, 18: 324, 19: 325, 20: 326, 21: 327, 22: 329, 23: 334, 24: 336,
      25: 338, 26: 339, 27: 350, 28: 351, 29: 352, 30: 353, 31: 354}

# ── 시트2 초도물품(권장) : 양식 행 → (통합리스트 행 | None, 비고)
S2 = {
    149: (376, "쌀 2행 중복(376·379) 동일가"), 150: (341, ""), 151: (342, ""), 152: (343, ""),
    153: (344, "규격 변경: 2.7kg/PK → 10.8kg/BOX(2.7kg×4)"), 154: (345, ""), 155: (346, ""),
    156: (347, ""), 157: (328, ""), 158: (337, ""),
    159: (20, "통합(전 브랜드) 음료"), 160: (21, "통합(전 브랜드) 음료"), 161: (19, "통합(전 브랜드) 음료"),
    162: (None, "코카콜라 병 — 통합리스트에 없음"), 163: (22, "통합(전 브랜드) 음료"),
    164: (None, "계란 특란(ODJ) — 옥된장/석문어 품목으로만 등록, 철산장 없음"),
    165: (360, ""), 166: (None, "함수결정포도당 — 통합리스트에 없음"), 167: (362, ""), 168: (358, ""),
    169: (359, ""), 170: (361, ""), 171: (381, ""), 172: (356, ""), 173: (357, ""), 174: (382, ""),
    175: (380, ""), 176: (None, "연두순 — 통합리스트에 없음"), 177: (363, ""),
    178: (None, "하얀설탕 — 석문어 품목으로만 등록, 철산장 없음"), 179: (384, ""), 180: (355, ""),
    181: (387, ""), 182: (385, ""), 183: (None, "배퓨레 — 통합리스트 '삭제' 표기"), 184: (386, ""),
    185: (383, ""), 186: (367, ""), 187: (368, ""), 188: (370, ""), 189: (390, ""), 190: (392, ""),
    191: (410, ""), 192: (409, "상품 변경: 움트리 강겨자 → 솔표 겨자분말"),
    193: (369, "상품 변경: 정성식품 → 치악산 들향기름"), 194: (395, ""), 195: (394, ""), 196: (391, ""),
    197: (389, ""), 198: (388, ""), 199: (393, ""), 200: (396, ""), 201: (372, ""), 202: (371, ""),
    203: (332, ""), 204: (401, ""), 205: (400, ""), 206: (404, ""), 207: (365, ""),
    208: (398, "화장지 2행 중복(398 15,530 / 399 15,500) — 398 적용"), 209: (397, ""),
    210: (None, "세척기용 중성세제 — 철산장 없음(브랜드 미지정 행만 있음). 식기세척기 세제(20KG) 신규행 확인"),
    211: (402, ""), 212: (408, ""), 213: (407, ""), 214: (405, ""), 215: (406, ""), 216: (403, ""),
}
RENAME = {192: ("겨자분말_솔표(200g)_EA", "EA"), 193: ("들향기름_치악산 (1.8L)_EA", "EA"),
          153: ("냉면김치 흰색 (중국산)", "10.8kg/BOX")}

# 양식에 없고 통합리스트 철산장에 있는 품목 → 시트2 끝에 추가 (규격 표기)
NEW = [(419, "BF 냉면육수 (냉동)", "2kg/PK", "강제여부 공란 — 강제/권장 확인 필요"),
       (377, "(과세)냉면용무김치(흰색)_그래도푸드 (2.8kg)_EA", "EA", ""),
       (364, "식기세척기 세제 (20KG)_EA", "EA", ""),
       (373, "제때 참기름_참고을(1.8L)_EA", "EA", ""),
       (374, "페이퍼핸드타올_대성산업 (5000EA)_BOX", "BOX", ""),
       (375, "부탄가스_맥선세이프 (4EA)_PK", "PK", ""),
       (378, "탄산수 씨그램 플레인(190ml*30개)_BOX", "BOX", ""),
       (194, "조미김가루_하늘비 (500g)_PK", "PK", "옥된장/철산장 공용"),
       (330, "야끼만두(잡채튀김)_만복식품 (1.2kg)_PK", "PK", "철산장 구역에 있으나 브랜드 칸 공란 — 확인"),
       (331, "사각어묵_오양(800g)_봉", "봉", "철산장 구역에 있으나 브랜드 칸 공란 — 확인")]

wb = openpyxl.load_workbook(FORM)

# 시트1
ws1 = wb.worksheets[0]
for fr, lr in S1.items():
    it = item(lr)
    old_p, old_t = ws1.cell(fr, 9).value, ws1.cell(fr, 10).value
    new_t = 기준문구(it)
    for col, old, new in ((9, old_p, it["공급가"]), (10, old_t, new_t)):
        if old != new:
            c = ws1.cell(fr, col)
            c.value = new
            f = copy(c.font); f.color = RED; c.font = f

# 시트2 — H·I열 추가
ws2 = wb.worksheets[1]
for col, title, width in ((8, "공급가격", 14), (9, "공급가격 결정기준", 95)):
    h = ws2.cell(4, col)
    h._style = copy(ws2.cell(4, 7)._style)
    h.value = title
    ws2.column_dimensions[h.column_letter].width = width
ws2.cell(148, 8)._style = copy(ws2.cell(148, 3)._style)


def put(r, col, value, red=False):
    c = ws2.cell(r, col)
    c._style = copy(ws2.cell(r, 7)._style)
    if col == 9:
        c.alignment = Alignment(horizontal="left", vertical="center")
    if col == 8:
        c.number_format = "#,##0"
    c.value = value
    if red:
        f = copy(c.font); f.color = RED; c.font = f


for fr, (lr, note) in S2.items():
    name = ws2.cell(fr, 3).value
    if fr in RENAME:
        for col, v in zip((3, 4), RENAME[fr]):
            c = ws2.cell(fr, col); c.value = v
            f = copy(c.font); f.color = RED; c.font = f
    if lr is None:
        put(fr, 8, None)
        put(fr, 9, f"[확인] {note}", red=True)
        continue
    it = item(lr)
    put(fr, 8, it["공급가"])
    put(fr, 9, 기준문구(it), red=it["구분"] == "범용")

last_no = ws2.cell(216, 2).value
tmpl = 216
for k, (lr, name, spec, note) in enumerate(NEW, 1):
    r = tmpl + k
    for col in range(2, 8):
        ws2.cell(r, col)._style = copy(ws2.cell(tmpl, col)._style)
    ws2.row_dimensions[r].height = ws2.row_dimensions[tmpl].height
    it = item(lr)
    vals = [last_no + k, name, spec, "(주)제때", "권장", "X"]
    for col, v in zip(range(2, 8), vals):
        c = ws2.cell(r, col); c.value = v
        f = copy(c.font); f.color = RED; c.font = f
    put(r, 8, it["공급가"], red=True)
    put(r, 9, 기준문구(it), red=True)

OUT_FORM.parent.mkdir(exist_ok=True)
try:
    wb.save(OUT_FORM)
except PermissionError:
    print("작성본이 엑셀에서 열려 있어 저장 건너뜀:", OUT_FORM.name)

# ── 대사표 : 통합리스트 철산장 품목이 베이스, 양식 품목은 거기에 매핑
# 양식 품목명·공급가는 물류세팅 때 임의 입력값이라 기준으로 쓰지 않음
FORM_TO_LIST = {("시트1", fr): lr for fr, lr in S1.items()}
FORM_TO_LIST.update({("시트2", fr): lr for fr, (lr, _) in S2.items() if lr})
NOTE = {("시트2", fr): n for fr, (_, n) in S2.items() if n}
# 작성본엔 공급가를 안 넣었지만 리스트에 다른 브랜드·삭제 행으로 존재하는 품목 (대사표 참조용)
FORM_TO_LIST.update({("시트2", 164): 110, ("시트2", 178): 105, ("시트2", 183): 411, ("시트2", 210): 295})

# 베이스 = 브랜드 칸에 철산장 포함 + 리스트 철산장 구역(324~419행) 브랜드 공란 행
base = []
for row in range(4, L.max_row + 1):
    it = item(row)
    if not it["품명"] or it["품명"] == "품명":
        continue
    if "철산장" in str(it["브랜드"] or "") or (324 <= row <= 419 and it["브랜드"] is None):
        base.append(it)
base_rows = {it["row"] for it in base}

# 양식 품목 전체 읽기 (구역명 포함)
src = openpyxl.load_workbook(FORM, data_only=True)
form_items = []
for key, ws_, first, last in (("시트1", src.worksheets[0], 6, 31), ("시트2", src.worksheets[1], 5, 216)):
    section = None
    for r in range(first, last + 1):
        b, c = ws_.cell(r, 2).value, ws_.cell(r, 3).value
        if isinstance(b, str) and b.strip():
            section = "용역" if b.strip() == "용 역" else b.strip()
        if c is None:
            continue
        if key == "시트1":
            d = dict(규격=ws_.cell(r, 4).value, 거래형태=ws_.cell(r, 5).value, 거래상대방=ws_.cell(r, 6).value,
                     차액=ws_.cell(r, 7).value, 공급가=ws_.cell(r, 9).value, 기준=ws_.cell(r, 10).value)
        else:
            d = dict(규격=ws_.cell(r, 4).value, 거래상대방=ws_.cell(r, 5).value, 거래형태=ws_.cell(r, 6).value,
                     차액=ws_.cell(r, 7).value, 공급가=None, 기준=None)
        form_items.append(dict(시트=key, 행=r, 구역=section, 순번=b if isinstance(b, int) else None, 품목=c, **d))

list_to_form = {}
for fi in form_items:
    lr = FORM_TO_LIST.get((fi["시트"], fi["행"]))
    if lr in base_rows:
        list_to_form[lr] = fi

thin = Side(style="thin", color="FFBFBFBF")
bd = Border(left=thin, right=thin, top=thin, bottom=thin)
F9, F9B = Font(name="맑은 고딕", size=9), Font(name="맑은 고딕", size=9, bold=True)
HEAD_FILL = PatternFill("solid", fgColor="FFD9D9D9")
FORM_FILL = PatternFill("solid", fgColor="FFDDEBF7")


def sheet(ws, title, sub, head, rows, widths, money=(), rate=(), form_cols=()):
    ws["A1"] = title
    ws["A1"].font = Font(name="맑은 고딕", size=12, bold=True)
    ws["A2"] = sub
    ws["A2"].font = F9
    ws.append([])
    ws.append(head)
    for i, c in enumerate(ws[4], 1):
        c.font = F9B; c.border = bd
        c.fill = FORM_FILL if i in form_cols else HEAD_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for vals, flag in rows:
        ws.append([None if v == "-" else v for v in vals])
        r = ws.max_row
        for c in ws[r]:
            c.font = F9; c.border = bd; c.alignment = Alignment(vertical="center")
            if flag:
                c.fill = MEMO_FILL
        for col in money:
            ws.cell(r, col).number_format = "#,##0"
        for col in rate:
            ws.cell(r, col).number_format = "0.0%"
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.freeze_panes = "E5"
    ws.auto_filter.ref = f"A4:{openpyxl.utils.get_column_letter(len(head))}{ws.max_row}"


def pct_in(text):
    m = re.search(r"([\d.]+)%", str(text or ""))
    return float(m.group(1)) / 100 if m else None


# 시트1 — 철산장 품목리스트 기준
rows1 = []
for it in base:
    fi = list_to_form.get(it["row"])
    notes = []
    if it["강제"] == "삭제":
        notes.append("리스트 '삭제' 표기")
    if it["브랜드"] is None:
        notes.append("브랜드 칸 공란(철산장 구역)")
    if it["강제"] is None:
        notes.append("강제여부 공란")
    if not isinstance(it["공급가"], (int, float)):
        notes.append("공급가 미정")
    price_ok = rate_ok = None
    if fi:
        if (fi["시트"], fi["행"]) in NOTE:
            notes.append(NOTE[(fi["시트"], fi["행"])])
        if fi["공급가"] is not None:
            price_ok = "일치" if fi["공급가"] == it["공급가"] else "불일치"
        fr = pct_in(fi["기준"])
        if fr is not None and isinstance(it["마진율"], (int, float)):
            rate_ok = "일치" if abs(fr - it["마진율"]) < 0.0005 else "불일치"
        if price_ok == "불일치" or rate_ok == "불일치":
            notes.append("양식 기재값과 다름")
    else:
        notes.append("양식에 없음")
    rows1.append(([it["row"], it["강제"], it["구분"], it["브랜드"], it["품명"], it["과세"], it["매입사"],
                   it["BT매입"], it["제때구매"], it["공급단가"], it["공급가"], it["마진율"], it["제때"], it["본사"], it["BT"],
                   fi and fi["시트"], fi and fi["순번"], fi and fi["품목"], fi and fi["규격"], fi and fi["거래형태"],
                   fi and fi["공급가"], fi and pct_in(fi["기준"]), price_ok, rate_ok, " / ".join(notes)],
                  bool(notes and notes != ["양식에 없음"]) or not fi))

# 시트2 — 양식에만 있는 품목
rows2 = []
for fi in form_items:
    lr = FORM_TO_LIST.get((fi["시트"], fi["행"]))
    if lr in base_rows:
        continue
    if fi["구역"] and "초도" in fi["구역"]:
        if lr:
            o = item(lr)
            o["브랜드"] = o["브랜드"] or "브랜드 미지정"
            kind = "초도물품 — 리스트에 타 브랜드·통합으로만 등록"
            ref = f"{lr}행 [{o['브랜드']}] {o['품명']} / 공급가 {o['공급가']:,}" if isinstance(o["공급가"], (int, float)) else f"{lr}행 [{o['브랜드']}] {o['품명']}"
        else:
            kind, ref = "초도물품 — 리스트 미등록", ""
        note = NOTE.get((fi["시트"], fi["행"]), "")
    else:
        kind, ref, note = "물류 외 품목(용역·의탁자·장비·집기)", "", ""
    rows2.append(([fi["시트"], fi["구역"], fi["순번"], fi["품목"], fi["규격"], fi["거래형태"], fi["거래상대방"],
                   fi["차액"], fi["공급가"], fi["기준"], kind, ref, note], kind.startswith("초도")))
order = {"초도물품 — 리스트 미등록": 0, "초도물품 — 리스트에 타 브랜드·통합으로만 등록": 1}
rows2.sort(key=lambda x: order.get(x[0][10], 2))

out = openpyxl.Workbook()
sheet(out.active, "철산장 정보공개서 별지1 대사표 — 2026년 9월 통합 품목리스트 철산장 품목 기준",
      "베이스 = 통합리스트 철산장 품목(강제여부·가격은 리스트 값) / 파란 헤더 = 양식(물류세팅 임의값) 매핑 / "
      "마진율 = (공급단가 − BT매입단가) ÷ 공급단가 / 색칠 행 = 확인 필요",
      ["리스트 행", "강제여부", "구분", "브랜드", "품명", "과세", "매입사", "BT매입단가", "제때구매단가", "공급단가",
       "공급가(VAT포함)", "총마진율", "제때", "가맹본부", "BT",
       "양식 시트", "양식 순번", "양식 품목", "양식 규격", "양식 거래형태", "양식 공급가", "양식 마진율",
       "공급가 비교", "마진율 비교", "비고"],
      rows1, [7, 7, 6, 12, 42, 6, 16, 10, 10, 10, 11, 8, 6, 7, 6, 7, 6, 28, 14, 8, 10, 8, 8, 8, 50],
      money=(8, 9, 10, 11, 21), rate=(12, 13, 14, 15, 22), form_cols=range(16, 23))
out.active.title = "철산장 품목리스트 기준"
sheet(out.create_sheet("양식에만 있는 품목"), "양식(가맹점 개설 견적 요청서)에만 있고 철산장 품목리스트에 없는 품목",
      "분류: 초도물품 리스트 미등록 → 타 브랜드·통합으로만 등록 → 물류 외 품목 순 / 색칠 행 = 초도물품(확인 필요)",
      ["양식 시트", "구역", "순번", "품목", "규격", "거래형태", "거래상대방", "차액가맹금", "양식 공급가", "양식 결정기준",
       "분류", "리스트 참고", "비고"],
      rows2, [7, 16, 6, 40, 18, 8, 22, 8, 11, 50, 30, 50, 45], money=(9,))
if OUT_CHECK.exists():
    print("대사표는 사용자가 직접 수정한 파일이라 덮어쓰지 않음:", OUT_CHECK.name)
else:
    out.save(OUT_CHECK)
print("saved", OUT_FORM.name, OUT_CHECK.name, "base", len(base), "mapped", len(list_to_form), "form-only", len(rows2))
