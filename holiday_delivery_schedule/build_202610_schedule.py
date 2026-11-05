# -*- coding: utf-8 -*-
"""2026년 10월 마켓봄 택배 배송일정표 (개천절·한글날)

택배사 통보(9/23 카톡):
  - 정재엽: 10/3~10/5, 10/9~10/11 택배사 휴무
  - 안재범: "10/1까지 발송, 10/6 재개" 확인. 한글날도 동일 패턴
  → 10/2 출고분은 도착일(10/3)이 휴무라 발송 불가 → 1차 마감 10/1(목)
  → 같은 논리로 10/8 출고분도 도착일(10/9)이 휴무 → 2차 마감 10/7(수)
  → 발송 중단이 두 번: 10/2~10/5(재개 10/6) / 10/8~10/11(재개 10/12)
  → 달력 3주(9/27~10/17). 마감·재개가 4번이라 연두(여유 주문 권장)는 쓰지 않음

구성 원칙 — 두 구역으로만 나눈다.
  구역 A  안내문  : 테두리 없음 · 왼쪽 정렬 (인사말~맺음말)
  구역 B  배송일정표 : 테두리 있는 한 덩어리 · 가운데 정렬
                    (강조 → 기준 → 요일 → 달력 → 유의사항)
"""
import sys

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = r"c:\Users\BLUETREND\류호정\bt\holiday_delivery_schedule\20260923_10월_택배_배송일정_마켓봄.xlsx"
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
ws.title = "10월 배송일정"
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
band(1, "[필독] 개천절 · 한글날 택배 배송 일정 안내",
     size=16, bold=True, align=L, border=None, height=30)
band(2, "등록일 : 2026-09-23", size=10, color="808080",
     align=R, border=None)

INTRO = [
    "",
    "안녕하세요.",
    "",
    "10월 개천절·한글날 연휴 기간 배송 일정이 아래와 같이 조정되오니,",
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
# 표 제목 — 표 바깥, A~G 한 줄로 병합해 가운데 정렬 (2026-09 사용자 수정 양식)
band(11, '10월 "마켓봄" 배송일정', size=18, bold=True, border=None, height=30)

# ① 강조 줄 — 표의 첫 행
band(12,
     "★ 10월에는 택배 발송이 두 차례 중단됩니다. (10/2~10/5 · 10/8~10/11)\n"
     "주문 마감도 10/1(목) · 10/7(수) 오전 9시 두 번이니, 각각 5일치 재고를 확보해 주시기 바랍니다.",
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
    ("9/27", None,   "FF0000"),  # 일
    ("28",   None,   "000000"),
    ("29",   None,   "000000"),
    ("30",   None,   "000000"),
    ("10/1", BLUE,   "000000"),  # 목 - 1차 주문 마감
    ("2",    YELLOW, "000000"),  # 금 - 입고 지연 우려
    ("3",    YELLOW, "FF0000"),  # 토 - 개천절
]
NOTE1 = [
    ("", None, "000000"),
    ("", None, "000000"),
    ("", None, "000000"),
    ("", None, "000000"),
    ("1차 주문마감\n→ 10/2 도착",        BLUE,   "000000"),
    ("발송 불가\n(입고 지연 우려)",        YELLOW, "000000"),
    ("발송 불가\n(개천절)",               YELLOW, "000000"),
]
WEEK2 = [
    ("4",    YELLOW, "FF0000"),  # 일
    ("5",    YELLOW, "FF0000"),  # 월 - 대체휴일
    ("10/6", BLUE,   "000000"),  # 화 - 발송 재개
    ("7",    BLUE,   "000000"),  # 수 - 2차 주문 마감
    ("8",    YELLOW, "000000"),  # 목 - 입고 지연 우려
    ("9",    YELLOW, "FF0000"),  # 금 - 한글날
    ("10",   YELLOW, "000000"),  # 토 - 연휴
]
NOTE2 = [
    ("발송 불가\n(일요일)",               YELLOW, "000000"),
    ("발송 불가\n(대체휴일)",              YELLOW, "000000"),
    ("발송 재개\n→ 10/7 도착",            BLUE,   "000000"),
    ("2차 주문마감\n→ 10/8 도착",        BLUE,   "000000"),
    ("발송 불가\n(입고 지연 우려)",        YELLOW, "000000"),
    ("발송 불가\n(한글날)",               YELLOW, "000000"),
    ("발송 불가\n(연휴)",                 YELLOW, "000000"),
]
WEEK3 = [
    ("11",    YELLOW, "FF0000"),  # 일
    ("10/12", BLUE,   "000000"),  # 월 - 발송 재개
    ("13",    None,   "000000"),
    ("14",    None,   "000000"),
    ("15",    None,   "000000"),
    ("16",    None,   "000000"),
    ("17",    None,   "000000"),
]
NOTE3 = [
    ("발송 불가\n(일요일)",            YELLOW, "000000"),
    ("발송 재개\n→ 10/13 도착",        BLUE,   "000000"),
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

# ⑤ 유의사항 — 표의 마지막 행들 (2026-09 사용자 수정 양식)
#    · 맺음말("감사합니다.")은 넣지 않는다 — 안내문(구역 A)에 이미 있다
#    · 줄 사이 가로 구분선 없이 바깥 테두리만 — 유의사항이 한 덩어리로 읽히게
FOOTER = [
    ("마켓봄 주문 마감 : 1차 10/1(목) 오전 9시 → 10/2(금) 도착 / 2차 10/7(수) 오전 9시 → 10/8(목) 도착", True,  "000000"),
    ("*마감 이후 주문은 각각 10/6(화)·10/12(월)에 출고되오니, 마감 전날까지 미리 주문해 주시기 바랍니다.",   True,  "C00000"),
    ("*본 안내는 택배 배송 품목 기준이며, 제주·도서산간은 1일 이상 추가 소요됩니다.",                     False, "000000"),
]
r = 21
for n, (text, bold, color) in enumerate(FOOTER):
    edge = Border(left=THIN, right=THIN,
                  top=THIN if n == 0 else None,
                  bottom=THIN if n == len(FOOTER) - 1 else None)
    band(r, text, size=10, bold=bold, color=color, border=edge)
    r += 1

# ── 인쇄 설정
ws.print_area = f"A1:G{r-1}"
ws.page_setup.orientation = "landscape"
ws.page_setup.fitToWidth = 1
ws.page_setup.fitToHeight = 1
ws.sheet_properties.pageSetUpPr.fitToPage = True

wb.save(OUT)
print("saved:", OUT)
