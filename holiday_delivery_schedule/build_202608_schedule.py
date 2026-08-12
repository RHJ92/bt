# -*- coding: utf-8 -*-
"""2026년 8월 마켓봄 택배 배송일정표 (택배없는날·광복절·대체휴일)

구성 원칙 — 두 구역으로만 나눈다.
  구역 A  안내문  : 테두리 없음 · 왼쪽 정렬 (인사말~맺음말)
  구역 B  배송일정표 : 테두리 있는 한 덩어리 · 가운데 정렬
                    (강조 → 기준 → 요일 → 달력 → 유의사항)
"""
import sys

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = r"c:\Users\BLUETREND\류호정\bt\holiday_delivery_schedule\20260810_8월_택배_배송일정_마켓봄.xlsx"
if len(sys.argv) > 1:          # 파일이 열려 있을 때 임시 경로로 미리보기
    OUT = sys.argv[1]

FONT = "맑은 고딕"

# ── 색상 (첨부 이미지 기준)
NAVY   = PatternFill("solid", fgColor="1F3864")   # 요일 헤더
GRAY   = PatternFill("solid", fgColor="D9D9D9")   # 지난 날짜
LGRAY  = PatternFill("solid", fgColor="F2F2F2")   # 기준 안내 줄
BLUE   = PatternFill("solid", fgColor="BDD7EE")   # 주문마감 / 발송재개
YELLOW = PatternFill("solid", fgColor="FFFF00")   # 택배 발송 불가
GREEN  = PatternFill("solid", fgColor="E2EFDA")   # 여유 주문 권장
IVORY  = PatternFill("solid", fgColor="FFF2CC")   # 강조 줄

THIN  = Side(style="thin",   color="000000")
THICK = Side(style="medium", color="C00000")
BOX   = Border(left=THIN,  right=THIN,  top=THIN,  bottom=THIN)
ALERT = Border(left=THICK, right=THICK, top=THICK, bottom=THICK)
C = Alignment(horizontal="center", vertical="center", wrap_text=True)
L = Alignment(horizontal="left",   vertical="center", wrap_text=True)
R = Alignment(horizontal="right",  vertical="center")

wb = Workbook()
ws = wb.active
ws.title = "8월 배송일정"
ws.sheet_view.showGridLines = False

for i in range(1, 8):
    ws.column_dimensions[get_column_letter(i)].width = 16


def put(cell, value, *, size=11, bold=False, color="000000",
        fill=None, align=C, border=BOX):
    c = ws[cell]
    c.value = value
    c.font = Font(name=FONT, size=size, bold=bold, color=color)
    c.alignment = align
    if fill:
        c.fill = fill
    if border:
        c.border = border
    return c


def band(row, text, *, size=10, bold=False, color="000000",
         fill=None, align=C, border=BOX, height=20):
    """A~G 병합 한 줄. 병합 구간 전체에 테두리·채움을 준다."""
    ws.merge_cells(f"A{row}:G{row}")
    put(f"A{row}", text, size=size, bold=bold, color=color,
        fill=fill, align=align, border=border)
    for i in range(1, 8):
        c = ws[f"{get_column_letter(i)}{row}"]
        if border:
            c.border = border
        if fill:
            c.fill = fill
    ws.row_dimensions[row].height = height


# ══════════════════════════════════════════════════════════
# 구역 A — 안내문 (테두리 없음 · 왼쪽 정렬)
# ══════════════════════════════════════════════════════════
band(1, "[필독] 8월 택배 배송 일정 안내 (택배없는날 · 광복절 · 대체휴일)",
     size=16, bold=True, align=L, border=None, height=30)
band(2, "등록일 : 2026-08-10", size=10, color="808080",
     align=R, border=None)

INTRO = [
    "",
    "안녕하세요.",
    "",
    "8월 배송 일정이 아래와 같이 조정되오니,",
    "일정 확인하시어 매장 운영에 차질 없도록 사전 주문 부탁드립니다.",
    "",
    "감사합니다.",
]
for i, line in enumerate(INTRO, start=3):
    band(i, line, size=11, align=L, border=None, height=18)

ws.row_dimensions[10].height = 14   # 구역 사이 여백

# ══════════════════════════════════════════════════════════
# 구역 B — 배송일정표 (테두리 있는 한 덩어리 · 가운데 정렬)
# ══════════════════════════════════════════════════════════
# 표 제목 (원본 양식과 동일하게 표 바깥)
ws.merge_cells("A11:B11")
put("A11", "8월", size=18, bold=True, align=L, border=None)
ws.merge_cells("C11:G11")
put("C11", '"마켓봄" 배송일정', size=18, bold=True, border=None)
ws.row_dimensions[11].height = 30

# ① 강조 줄 — 표의 첫 행
band(12,
     "★ 8/13(목) ~ 8/17(월) 5일간 택배 발송이 중단됩니다.\n"
     "8/13(목) 도착분으로 8/19(수)까지 운영하셔야 하니, 재고를 넉넉히 확보해 주시기 바랍니다.",
     size=12, bold=True, color="C00000", fill=IVORY,
     border=ALERT, height=48)

# ② 기준 줄
band(13, "※ 날짜는 출고(발송) 기준이며, 매장 도착은 출고 다음 날입니다.",
     size=10, bold=True, color="1F3864", fill=LGRAY, height=20)

# ③ 요일 헤더
DAYS = ["일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일"]
for i, d in enumerate(DAYS, start=1):
    put(f"{get_column_letter(i)}14", d, size=11, bold=True,
        color="FFFFFF", fill=NAVY)
ws.row_dimensions[14].height = 24

# ④ 달력 (표시값, 채움, 글자색)
WEEK1 = [
    ("9",    GRAY,   "FF0000"),  # 일 (지난 날짜)
    ("10",   None,   "000000"),  # 월
    ("11",   GREEN,  "000000"),  # 화 - 여유 주문 권장
    ("8/12", BLUE,   "000000"),  # 수 - 주문 마감
    ("13",   YELLOW, "000000"),  # 목 - 집하 불가
    ("14",   YELLOW, "000000"),  # 금 - 택배없는날
    ("15",   YELLOW, "FF0000"),  # 토 - 광복절
]
NOTE1 = [
    ("",                                  GRAY,   "000000"),
    ("",                                  None,   "000000"),
    ("여유 주문 권장",                       GREEN,  "375623"),
    ("오전 9시 주문마감\n당일출고 → 8/13 도착", BLUE,   "000000"),
    ("발송 불가\n※ 8/12 출고분 도착은 정상",   YELLOW, "000000"),
    ("발송 불가\n(택배없는날)",               YELLOW, "000000"),
    ("발송 불가\n(광복절)",                  YELLOW, "000000"),
]
WEEK2 = [
    ("16",   YELLOW, "FF0000"),  # 일
    ("17",   YELLOW, "000000"),  # 월 - 대체휴일
    ("8/18", BLUE,   "000000"),  # 화 - 발송 재개
    ("19",   None,   "000000"),
    ("20",   None,   "000000"),
    ("21",   None,   "000000"),
    ("22",   None,   "000000"),
]
NOTE2 = [
    ("발송 불가\n(일요일)",           YELLOW, "000000"),
    ("발송 불가\n(대체휴일)",          YELLOW, "000000"),
    ("발송 재개\n→ 8/19 도착 예정",    BLUE,   "000000"),
    ("", None, "000000"),
    ("", None, "000000"),
    ("", None, "000000"),
    ("", None, "000000"),
]

for row, dates, notes in ((15, WEEK1, NOTE1), (17, WEEK2, NOTE2)):
    for i, (val, fill, color) in enumerate(dates, start=1):
        put(f"{get_column_letter(i)}{row}", val, size=12,
            bold=True, color=color, fill=fill)
    for i, (val, fill, color) in enumerate(notes, start=1):
        put(f"{get_column_letter(i)}{row+1}", val, size=10,
            bold=True, color=color, fill=fill)
    ws.row_dimensions[row].height = 24
    ws.row_dimensions[row + 1].height = 38

# ⑤ 유의사항 — 표의 마지막 행들
FOOTER = [
    ("마켓봄 주문 마감 : 8/12(수) 오전 9시 (당일 출고 → 8/13(목) 도착)",          True,  "000000"),
    ("*연휴 직전 물량이 몰려 지연될 수 있으니, 8/11(화) 이전 주문을 권장드립니다.",  True,  "C00000"),
    ("*본 안내는 택배 배송 품목 기준이며, 제주·도서산간은 1일 이상 추가 소요됩니다.", False, "000000"),
    ("감사합니다.",                                                        False, "000000"),
]
r = 19
for text, bold, color in FOOTER:
    band(r, text, size=10, bold=bold, color=color)
    r += 1

# ── 인쇄 설정
ws.print_area = f"A1:G{r-1}"
ws.page_setup.orientation = "landscape"
ws.page_setup.fitToWidth = 1
ws.page_setup.fitToHeight = 1
ws.sheet_properties.pageSetUpPr.fitToPage = True

wb.save(OUT)
print("saved:", OUT)
