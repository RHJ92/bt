# -*- coding: utf-8 -*-
"""2026년 추석 마켓봄 택배 배송일정표

택배사 통보(9/11): 9/21(월)까지 반출 가능 / 9/22(화)~9/27(일) 휴무
  → 9/21 출고분은 연휴 전 물량 몰림으로 9/22~9/23 도착 — 연휴 전 입고 보장 안 됨
최종안(9/11 사용자 확정): 주문 마감 9/18(금) 오전 9시, 9/21은 발송 불가로 안내
  → 발송 중단 9/19(토)~9/27(일) = 9일, 9/28(월) 재개
  → 마감일이 연휴 전 주로 넘어가 달력을 3주(9/13~10/3)로 늘림

구성 원칙 — 두 구역으로만 나눈다.
  구역 A  안내문  : 테두리 없음 · 왼쪽 정렬 (인사말~맺음말)
  구역 B  배송일정표 : 테두리 있는 한 덩어리 · 가운데 정렬
                    (강조 → 기준 → 요일 → 달력 → 유의사항)
"""
import sys

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = r"c:\Users\BLUETREND\류호정\bt\holiday_delivery_schedule\20260911_추석_택배_배송일정_마켓봄.xlsx"
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
ws.title = "추석 배송일정"
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
band(1, "[필독] 추석 연휴 택배 배송 일정 안내",
     size=16, bold=True, align=L, border=None, height=30)
band(2, "등록일 : 2026-09-11", size=10, color="808080",
     align=R, border=None)

INTRO = [
    "",
    "안녕하세요.",
    "",
    "추석 연휴 기간 배송 일정이 아래와 같이 조정되오니,",
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
put("A11", "추석", size=18, bold=True, align=L, border=None)
ws.merge_cells("C11:G11")
put("C11", '"마켓봄" 배송일정', size=18, bold=True, border=None)
ws.row_dimensions[11].height = 30

# ① 강조 줄 — 표의 첫 행
band(12,
     "★ 9/19(토) ~ 9/27(일) 9일간 택배 발송이 중단됩니다.\n"
     "9/18(금) 출고분으로 9/29(화)까지 운영하셔야 하니, 재고를 넉넉히 확보해 주시기 바랍니다.",
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
    ("13",   None,   "FF0000"),  # 일
    ("14",   None,   "000000"),
    ("15",   None,   "000000"),
    ("16",   None,   "000000"),
    ("17",   GREEN,  "000000"),  # 목 - 여유 주문 권장
    ("9/18", BLUE,   "000000"),  # 금 - 주문 마감
    ("19",   YELLOW, "000000"),  # 토 - 주말
]
NOTE1 = [
    ("", None, "000000"),
    ("", None, "000000"),
    ("", None, "000000"),
    ("", None, "000000"),
    ("여유 주문 권장",                       GREEN,  "375623"),
    ("오전 9시 주문마감\n→ 연휴 전 도착",       BLUE,   "000000"),
    ("발송 불가\n(주말)",                    YELLOW, "000000"),
]
WEEK2 = [
    ("20",   YELLOW, "FF0000"),  # 일 - 주말
    ("21",   YELLOW, "000000"),  # 월 - 연휴 전 도착 불가
    ("22",   YELLOW, "000000"),  # 화 - 택배 휴무
    ("23",   YELLOW, "000000"),  # 수 - 택배 휴무
    ("24",   YELLOW, "FF0000"),  # 목 - 추석 연휴
    ("25",   YELLOW, "FF0000"),  # 금 - 추석
    ("26",   YELLOW, "FF0000"),  # 토 - 추석 연휴
]
NOTE2 = [
    ("발송 불가\n(주말)",                    YELLOW, "000000"),
    ("발송 불가\n(입고 지연 우려)",           YELLOW, "000000"),
    ("발송 불가\n(입고 지연 우려)",           YELLOW, "000000"),
    ("발송 불가\n(입고 지연 우려)",           YELLOW, "000000"),
    ("발송 불가\n(추석 연휴)",               YELLOW, "000000"),
    ("발송 불가\n(추석)",                   YELLOW, "000000"),
    ("발송 불가\n(추석 연휴)",               YELLOW, "000000"),
]
WEEK3 = [
    ("27",   YELLOW, "FF0000"),  # 일
    ("9/28", BLUE,   "000000"),  # 월 - 발송 재개
    ("29",   None,   "000000"),
    ("30",   None,   "000000"),
    ("10/1", None,   "000000"),
    ("2",    None,   "000000"),
    ("3",    None,   "FF0000"),  # 토 - 개천절
]
NOTE3 = [
    ("발송 불가\n(일요일)",           YELLOW, "000000"),
    ("발송 재개\n→ 9/29 도착 예정",    BLUE,   "000000"),
    ("", None, "000000"),
    ("", None, "000000"),
    ("", None, "000000"),
    ("", None, "000000"),
    ("", None, "000000"),
]

for row, dates, notes in ((15, WEEK1, NOTE1), (17, WEEK2, NOTE2), (19, WEEK3, NOTE3)):
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
    ("마켓봄 주문 마감 : 9/18(금) 오전 9시 (당일 출고 → 추석 연휴 전 도착)",                    True,  "000000"),
    ("*9/18(금) 오전 9시 이후 주문은 9/28(월)에 출고되오니, 9/17(목)까지 미리 주문해 주시기 바랍니다.", True,  "C00000"),
    ("*본 안내는 택배 배송 품목 기준이며, 제주·도서산간은 1일 이상 추가 소요됩니다.",              False, "000000"),
    ("감사합니다.",                                                                  False, "000000"),
]
r = 21
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
