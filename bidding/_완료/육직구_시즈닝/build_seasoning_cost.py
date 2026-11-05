# -*- coding: utf-8 -*-
"""육직구 시즈닝 전용화 — 단가 타당성 검토 엑셀 생성.
엑셀을 손으로 고치지 말고 이 스크립트를 고쳐서 다시 돌린다.
    python build_seasoning_cost.py            # 원본 경로에 저장
    python build_seasoning_cost.py 미리보기.xlsx  # 파일이 열려 있을 때 임시 저장
"""
import sys, os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

NAVY = "1F3864"
SUB = "D9E2F3"
INPUT = "DDEBF7"      # 파란 셀 = 직접 입력
CALC = "F2F2F2"
WARN = "FFF2CC"
RED = "C00000"

thin = Side(style="thin", color="BFBFBF")
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)

WON = '#,##0'
WON2 = '#,##0.0'
PCT = '0.0%'

F = "맑은 고딕"


def st(c, *, b=False, size=10, color="000000", fill=None, align=None, fmt=None, wrap=False):
    c.font = Font(name=F, bold=b, size=size, color=color)
    if fill:
        c.fill = PatternFill("solid", fgColor=fill)
    c.alignment = Alignment(horizontal=align or "left", vertical="center", wrap_text=wrap)
    if fmt:
        c.number_format = fmt
    c.border = BOX
    return c


def head(ws, row, labels, widths=None):
    for i, t in enumerate(labels, 1):
        st(ws.cell(row=row, column=i, value=t), b=True, color="FFFFFF", fill=NAVY, align="center", wrap=True)
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def section(ws, row, text):
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(name=F, bold=True, size=11, color=NAVY)
    c.alignment = Alignment(horizontal="left", vertical="center")
    c.fill = PatternFill("solid", fgColor=SUB)
    for col in range(2, 11):
        ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=SUB)


# ── 기준 데이터 (품목리스트 2026-08-12 기준) ───────────────────────────
ITEMS = [
    # 품명, 현행매입가, 현행공급가, 월사용량(1개점), 시즈닝적용
    ("구이삼겹살(독일/테니시)", 8000, 12000, 273, True),
    ("목살(캐나다/올리멜)", 9100, 13000, 437, True),
    ("항정살(스페인/프리빈)", 14200, 17850, 134, True),
    ("삼겹양지(미국/엑셀)", 11150, 13000, 58, True),
    ("대패삼겹살(독일/시몬)", 8500, 11800, 144, True),
    ("목전지(미국/스미스필드)", 6500, 9000, 306, False),
]


def build(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "단가검토"
    ws.sheet_view.showGridLines = False

    c = ws.cell(row=1, column=1, value="육직구 시즈닝 전용화 — 단가 타당성 검토")
    c.font = Font(name=F, bold=True, size=15, color=NAVY)
    c = ws.cell(row=2, column=1,
                value="기준일 2026-08-12 · 정담(박주효 대표) 카톡 회신 기준 · 단위 원/kg, VAT 별도 · 파란 셀은 직접 입력")
    c.font = Font(name=F, size=9, color="595959")

    for i, w in enumerate([30, 14, 14, 14, 14, 14, 14, 14, 13, 34], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── [1] 기본 가정 ────────────────────────────────────────────────
    r = 4
    section(ws, r, "[1] 기본 가정")
    r += 1
    head(ws, r, ["항목", "값", "", "", "", "", "", "", "", "비고"])
    rows1 = [
        ("세절·염지 수율", 0.95, PCT, INPUT, "★ 미확인 — 정담 확인 필요. 원가를 가장 크게 좌우"),
        ("물류비율", 0.045, PCT, INPUT, "품목리스트 기준"),
        ("축산 마진율 상한", 0.15, PCT, INPUT, "내부 기준"),
        ("부가세율", 0.10, PCT, INPUT, "면세 → 과세 전환"),
        ("월 사용량 — 구이삼겹살 1개점(kg)", 273, WON, INPUT, "★ 입고량 기준이라 실사용량보다 과대 가능"),
    ]
    R_YIELD = r + 1
    for i, (nm, v, fmt, fill, memo) in enumerate(rows1):
        rr = r + 1 + i
        st(ws.cell(row=rr, column=1, value=nm), b=True, fill=CALC)
        st(ws.cell(row=rr, column=2, value=v), align="center", fmt=fmt, fill=fill)
        st(ws.cell(row=rr, column=10, value=memo), size=9,
           color=RED if "★" in memo else "595959", wrap=True)
    R_LOG, R_CAP, R_VAT, R_QTY = R_YIELD + 1, R_YIELD + 2, R_YIELD + 3, R_YIELD + 4

    # ── [2] 시즈닝 배합 원가 ─────────────────────────────────────────
    r = R_QTY + 2
    section(ws, r, "[2] 시즈닝 배합 원가   ※ 원료 포장단가를 넣으면 자동 계산")
    r += 1
    head(ws, r, ["원료", "배합량(g)", "포장단위(kg)", "포장단가(원)", "kg당 단가", "배합 투입액", "", "", "", "비고"])
    mix = [("맛소금", 750, 2, "미원 맛소금 / 정제염+MSG 혼합"),
           ("후추", 1000, 1, "투입량 확인됨 (08-12 카톡)"),
           ("연육제(푸로짐 에스)", 500, 1, "★ 면세 불가 사유 — 인산염 포함")]
    R_MIX0 = r + 1
    for i, (nm, g, pk, memo) in enumerate(mix):
        rr = R_MIX0 + i
        st(ws.cell(row=rr, column=1, value=nm), b=True, fill=CALC)
        st(ws.cell(row=rr, column=2, value=g), align="center", fmt=WON)
        st(ws.cell(row=rr, column=3, value=pk), align="center", fmt=WON2, fill=INPUT)
        st(ws.cell(row=rr, column=4, value=0), align="center", fmt=WON, fill=INPUT)
        st(ws.cell(row=rr, column=5, value=f"=IF(C{rr}=0,0,D{rr}/C{rr})"), align="center", fmt=WON)
        st(ws.cell(row=rr, column=6, value=f"=E{rr}*B{rr}/1000"), align="center", fmt=WON)
        st(ws.cell(row=rr, column=10, value=memo), size=9,
           color=RED if "★" in memo else "595959", wrap=True)
    R_MIX9 = R_MIX0 + len(mix) - 1
    R_MSUM = R_MIX9 + 1
    st(ws.cell(row=R_MSUM, column=1, value="합계 (1배치)"), b=True, fill=SUB)
    st(ws.cell(row=R_MSUM, column=2, value=f"=SUM(B{R_MIX0}:B{R_MIX9})"), b=True, align="center", fmt=WON, fill=SUB)
    for col in (3, 4, 5):
        st(ws.cell(row=R_MSUM, column=col), fill=SUB)
    st(ws.cell(row=R_MSUM, column=6, value=f"=SUM(F{R_MIX0}:F{R_MIX9})"), b=True, align="center", fmt=WON, fill=SUB)
    for col in range(7, 11):
        st(ws.cell(row=R_MSUM, column=col), fill=SUB)

    R_KG = R_MSUM + 1
    st(ws.cell(row=R_KG, column=1, value="배합 1kg당 단가(원)"), b=True, fill=CALC)
    st(ws.cell(row=R_KG, column=2, value=f"=IF(B{R_MSUM}=0,0,F{R_MSUM}/(B{R_MSUM}/1000))"),
       align="center", fmt=WON)
    st(ws.cell(row=R_KG, column=10, value="배합 투입액 ÷ 배합 중량"), size=9, color="595959")

    R_DOSE = R_KG + 1
    st(ws.cell(row=R_DOSE, column=1, value="육류 1kg당 투입량(g)"), b=True, fill=CALC)
    st(ws.cell(row=R_DOSE, column=2, value=9.45), align="center", fmt=WON2, fill=INPUT)
    st(ws.cell(row=R_DOSE, column=10, value="고기 3kg당 1온즈(28.35g) = 약 0.95%"), size=9, color="595959")

    R_SCOST = R_DOSE + 1
    st(ws.cell(row=R_SCOST, column=1, value="육류 1kg당 시즈닝 원가(원)"), b=True, fill=WARN)
    st(ws.cell(row=R_SCOST, column=2, value=f"=B{R_KG}*B{R_DOSE}/1000"), b=True, align="center", fmt=WON2, fill=WARN)
    st(ws.cell(row=R_SCOST, column=10, value="→ [3] 역산에 사용"), size=9, color="595959")

    # ── [3] 정담 제시가 역산 ─────────────────────────────────────────
    r = R_SCOST + 2
    section(ws, r, "[3] 견적 재산출 — 구이삼겹살 (당사 원물 구매가 기준)")
    r += 1
    head(ws, r, ["항목", "금액", "", "", "", "", "", "", "", "산식 · 근거"])
    R_Q = r + 1
    q = [
        ("정담 원안 · 원물 매입가", WON, INPUT, "정담이 전제한 삼겹 원물가 (08-12 카톡)"),
        ("정담 원안 · 완제품 단가", WON, INPUT, "세절 및 염지 작업 단가 (08-12 카톡)"),
        ("가공 부가분", WON, CALC, "원안 완제품가 − 원안 원물가. 재산출 시 동일 적용"),
        ("당사 원물 구매가", WON, INPUT, "★ 실제 구매 단가"),
        ("재산출 완제품 단가", WON, WARN, "당사 원물 구매가 + 가공 부가분 → 이하 계산에 적용"),
        ("수율 반영 원물원가", WON, CALC, "당사 원물 구매가 ÷ 수율"),
        ("시즈닝 원가", WON2, CALC, "[2] 산출값"),
        ("역산 가공비", WON, WARN, "재산출 단가 − 수율반영 원물원가 − 시즈닝 원가"),
        ("가공비 비중", PCT, WARN, "역산 가공비 ÷ 재산출 단가"),
        ("현행 매입가 대비 증감", WON, WARN, "현행 구이삼겹살 매입가 8,000원 기준"),
        ("증감률", PCT, WARN, ""),
    ]
    for i, (nm, fmt, fill, memo) in enumerate(q):
        rr = R_Q + i
        st(ws.cell(row=rr, column=1, value=nm), b=True, fill=CALC)
        st(ws.cell(row=rr, column=10, value=memo), size=9,
           color=RED if "★" in memo else "595959", wrap=True)
        st(ws.cell(row=rr, column=2), align="center", fmt=fmt, fill=fill)
    R_OLDRAW, R_OLDQ, R_ADD = R_Q, R_Q + 1, R_Q + 2
    R_RAW, R_PRICE = R_Q + 3, R_Q + 4
    ws.cell(row=R_OLDRAW, column=2, value=7200)
    ws.cell(row=R_OLDQ, column=2, value=9600)
    ws.cell(row=R_ADD, column=2, value=f"=B{R_OLDQ}-B{R_OLDRAW}")
    ws.cell(row=R_RAW, column=2, value=6900)
    ws.cell(row=R_PRICE, column=2, value=f"=B{R_RAW}+B{R_ADD}")
    ws.cell(row=R_Q + 5, column=2, value=f"=IF($B${R_YIELD}=0,0,B{R_RAW}/$B${R_YIELD})")
    ws.cell(row=R_Q + 6, column=2, value=f"=B{R_SCOST}")
    ws.cell(row=R_Q + 7, column=2, value=f"=B{R_PRICE}-B{R_Q+5}-B{R_Q+6}")
    ws.cell(row=R_Q + 8, column=2, value=f"=IF(B{R_PRICE}=0,0,B{R_Q+7}/B{R_PRICE})")
    ws.cell(row=R_Q + 9, column=2, value=f"=B{R_PRICE}-8000")
    ws.cell(row=R_Q + 10, column=2, value=f"=B{R_Q+9}/8000")

    # ── [3-1] 에치알푸드 대비 원가 구성 비교 ─────────────────────────
    r = R_Q + 12
    section(ws, r, "[3-1] 원가 구성 비교 — 에치알푸드 단순 세절 견적 대비 (동일 원물 6,900원 기준)")
    r += 1
    head(ws, r, ["구분", "원료육", "가공비", "부자재·물류비", "납품가", "", "", "", "", "비고"])
    R_H0 = r + 1
    hr = [
        ("에치알푸드 · 세절만", 6900, 700, 200, 8000, CALC,
         "2026-07-21 견적 · 오산 제때 물류 입고 기준 · 10kg 벌크 포장. 수율 3% 반영 시 8,013원"),
        ("정담 · 세절 + 염지", f"=$B${R_RAW}", f"=$B${R_ADD}", None, f"=$B${R_PRICE}", CALC,
         "가공비 2,400원은 세절·염지 일괄. 부자재·물류비 포함 여부 미확인"),
        ("염지 추가분", None, None, None, None, WARN,
         "시즈닝 공정 추가로 늘어나는 금액. 시즈닝 원료비는 kg당 200원 내외로 추정"),
    ]
    for i, (nm, raw, proc, pack, deliv, fill, memo) in enumerate(hr):
        rr = R_H0 + i
        st(ws.cell(row=rr, column=1, value=nm), b=True, fill=CALC)
        for col, v in ((2, raw), (3, proc), (4, pack), (5, deliv)):
            st(ws.cell(row=rr, column=col, value=v), align="center", fmt=WON, fill=fill)
        st(ws.cell(row=rr, column=10, value=memo), size=9, color="595959", wrap=True)
    ws.cell(row=R_H0 + 1, column=4, value="미확인").alignment = Alignment(horizontal="center", vertical="center")
    ws.cell(row=R_H0 + 2, column=5, value=f"=E{R_H0+1}-E{R_H0}")
    st(ws.cell(row=R_H0 + 2, column=5), b=True, align="center", fmt=WON, fill=WARN)

    # ── [4] 공급가·마진 시나리오 ─────────────────────────────────────
    r = R_H0 + 4
    section(ws, r, "[4] 공급가·마진 시나리오 — 구이삼겹살")
    r += 1
    head(ws, r, ["시나리오", "매입가", "공급가", "마진율", "물류비", "순마진", "순마진율", "과세", "", "비고"])
    R_S0 = r + 1
    scen = [
        ("① 현행 (시즈닝 전, 실제)", "8000", "12000", "면세", "마진 33.3% — 이미 상한 초과 상태"),
        ("② 현행 매입가 · 마진 15%", "8000", f"=B{R_S0+1}/(1-$B${R_CAP})", "면세",
         "★ 진짜 비교 기준선 — 시즈닝 안 해도 상한 지키면 여기"),
        ("③ 정담안 · 공급가 유지", f"=$B${R_PRICE}", "12000", "과세", "마진이 얼마나 깎이는지"),
        ("④ 정담안 · 마진 15%", f"=$B${R_PRICE}", f"=B{R_S0+3}/(1-$B${R_CAP})", "과세",
         "★ ②와 비교할 것 — 시즈닝 전환의 실질 효과"),
        ("⑤ 정담안 · 현행 마진율 유지", f"=$B${R_PRICE}", f"=B{R_S0+4}/(1-$D${R_S0})", "과세", "점주 공급가 인상폭"),
    ]
    for i, (nm, buy, sup, tax, memo) in enumerate(scen):
        rr = R_S0 + i
        st(ws.cell(row=rr, column=1, value=nm), b=True, fill=CALC)
        st(ws.cell(row=rr, column=2, value=buy), align="center", fmt=WON)
        st(ws.cell(row=rr, column=3, value=sup), align="center", fmt=WON)
        st(ws.cell(row=rr, column=4, value=f"=IF(C{rr}=0,0,1-B{rr}/C{rr})"), align="center", fmt=PCT)
        st(ws.cell(row=rr, column=5, value=f"=C{rr}*$B${R_LOG}"), align="center", fmt=WON)
        st(ws.cell(row=rr, column=6, value=f"=C{rr}-B{rr}-E{rr}"), align="center", fmt=WON)
        st(ws.cell(row=rr, column=7, value=f"=IF(C{rr}=0,0,F{rr}/C{rr})"), align="center", fmt=PCT)
        st(ws.cell(row=rr, column=8, value=tax), align="center")
        st(ws.cell(row=rr, column=10, value=memo), size=9, color="595959", wrap=True)

    # ── [4-1] 시즈닝 전환의 실질 효과 ────────────────────────────────
    R_B, R_A = R_S0 + 1, R_S0 + 3          # ② 기준선, ④ 정담안
    r = R_S0 + len(scen) + 1
    section(ws, r, "[4-1] 시즈닝 전환의 실질 효과 — ② 대비 ④ (마진 15% 상한 동일 조건)")
    r += 1
    head(ws, r, ["항목", "② 시즈닝 전", "④ 시즈닝 후", "증감", "증감률", "", "", "", "", "비고"])
    R_C = r + 1
    cmp_rows = [
        ("매입가", f"=B{R_B}", f"=B{R_A}", WON, "본사 매입원가"),
        ("공급가", f"=C{R_B}", f"=C{R_A}", WON, "점주 공급가"),
        ("순마진 (원/kg)", f"=F{R_B}", f"=F{R_A}", WON, "공급가 − 매입가 − 물류비"),
        ("월 순마진 (1개점)", f"=F{R_B}*$B${R_QTY}", f"=F{R_A}*$B${R_QTY}", WON, "[1] 월 사용량 연동"),
    ]
    for i, (nm, b, a, fmt, memo) in enumerate(cmp_rows):
        rr = R_C + i
        st(ws.cell(row=rr, column=1, value=nm), b=True, fill=CALC)
        st(ws.cell(row=rr, column=2, value=b), align="center", fmt=fmt)
        st(ws.cell(row=rr, column=3, value=a), align="center", fmt=fmt)
        st(ws.cell(row=rr, column=4, value=f"=C{rr}-B{rr}"), b=True, align="center", fmt=fmt, fill=WARN)
        st(ws.cell(row=rr, column=5, value=f"=IF(B{rr}=0,0,D{rr}/B{rr})"), b=True, align="center", fmt=PCT, fill=WARN)
        st(ws.cell(row=rr, column=10, value=memo), size=9, color="595959", wrap=True)

    # ── [5] 과세 전환 영향 ───────────────────────────────────────────
    r = R_C + len(cmp_rows) + 1
    section(ws, r, "[5] 과세 전환 영향 — ④ 정담안 · 마진 15% 기준")
    r += 1
    head(ws, r, ["항목", "금액", "", "", "", "", "", "", "", "비고"])
    R_T = r + 1
    tax_rows = [
        ("공급가 (VAT 별도)", f"=C{R_A}", WON, "④ 정담안 · 마진 15%"),
        ("부가세", f"=B{R_T}*$B${R_VAT}", WON, ""),
        ("점주 결제액 (VAT 포함)", f"=B{R_T}+B{R_T+1}", WON, ""),
        ("점주 실부담 — 일반과세자", 0, WON, "매입세액 공제로 실부담 없음"),
        ("점주 실부담 — 간이·면세사업자", f"=B{R_T+1}", WON, "전액 부담"),
    ]
    for i, (nm, v, fmt, memo) in enumerate(tax_rows):
        rr = R_T + i
        st(ws.cell(row=rr, column=1, value=nm), b=True, fill=CALC)
        st(ws.cell(row=rr, column=2, value=v), align="center", fmt=fmt)
        st(ws.cell(row=rr, column=10, value=memo), size=9, color="595959", wrap=True)

    # ── [6] 월간 금액 영향 ───────────────────────────────────────────
    r = R_T + len(tax_rows) + 1
    section(ws, r, "[6] 월간 금액 영향 — 구이삼겹살")
    r += 1
    head(ws, r, ["구분", "1개점", "2개점", "", "", "", "", "", "", "비고"])
    R_M = r + 1
    st(ws.cell(row=R_M, column=1, value="월 사용량(kg)"), b=True, fill=CALC)
    st(ws.cell(row=R_M, column=2, value=f"=$B${R_QTY}"), align="center", fmt=WON)
    st(ws.cell(row=R_M, column=3, value=f"=B{R_M}*1.75"), align="center", fmt=WON)
    st(ws.cell(row=R_M, column=10, value="[1] 연동 · 2개점은 ×1.75 배율"), size=9, color="595959", wrap=True)
    for i, (nm, expr) in enumerate([
            ("현행 매입액", "*8000"), ("정담안 매입액", f"*$B${R_PRICE}")]):
        rr = R_M + 1 + i
        st(ws.cell(row=rr, column=1, value=nm), b=True, fill=CALC)
        st(ws.cell(row=rr, column=2, value=f"=B{R_M}{expr}"), align="center", fmt=WON)
        st(ws.cell(row=rr, column=3, value=f"=C{R_M}{expr}"), align="center", fmt=WON)
        st(ws.cell(row=rr, column=10), size=9)
    rr = R_M + 3
    st(ws.cell(row=rr, column=1, value="증가액"), b=True, fill=WARN)
    st(ws.cell(row=rr, column=2, value=f"=B{R_M+2}-B{R_M+1}"), b=True, align="center", fmt=WON, fill=WARN)
    st(ws.cell(row=rr, column=3, value=f"=C{R_M+2}-C{R_M+1}"), b=True, align="center", fmt=WON, fill=WARN)
    st(ws.cell(row=rr, column=10, value="본사 매입원가 증가분"), size=9, color="595959")

    # ── [7] 6종 확장 ────────────────────────────────────────────────
    r = rr + 2
    section(ws, r, "[7] 대상 6종 — 견적 수령 시 원물매입가·제시가만 채우면 자동 계산")
    r += 1
    head(ws, r, ["품목", "현행 매입가", "현행 공급가", "원물 매입가", "정담 제시가",
                 "수율반영 원물원가", "시즈닝 원가", "역산 가공비", "매입가 증감", "마진 15% 공급가"])
    R_I0 = r + 1
    for i, (nm, buy, sup, qty, seasoned) in enumerate(ITEMS):
        rr2 = R_I0 + i
        st(ws.cell(row=rr2, column=1, value=nm), b=True, fill=CALC)
        st(ws.cell(row=rr2, column=2, value=buy), align="center", fmt=WON)
        st(ws.cell(row=rr2, column=3, value=sup), align="center", fmt=WON)
        st(ws.cell(row=rr2, column=4, value=(f"=$B${R_RAW}" if i == 0 else None)), align="center", fmt=WON, fill=INPUT)
        st(ws.cell(row=rr2, column=5, value=(f"=$B${R_PRICE}" if i == 0 else None)), align="center", fmt=WON, fill=INPUT)
        st(ws.cell(row=rr2, column=6, value=f"=IF(D{rr2}=\"\",\"\",IF($B${R_YIELD}=0,0,D{rr2}/$B${R_YIELD}))"),
           align="center", fmt=WON)
        st(ws.cell(row=rr2, column=7, value=(f"=$B${R_SCOST}" if seasoned else 0)), align="center", fmt=WON2)
        st(ws.cell(row=rr2, column=8, value=f"=IF(OR(E{rr2}=\"\",D{rr2}=\"\"),\"\",E{rr2}-F{rr2}-G{rr2})"),
           align="center", fmt=WON)
        st(ws.cell(row=rr2, column=9, value=f"=IF(E{rr2}=\"\",\"\",E{rr2}-B{rr2})"), align="center", fmt=WON)
        st(ws.cell(row=rr2, column=10, value=f"=IF(E{rr2}=\"\",\"\",E{rr2}/(1-$B${R_CAP}))"), align="center", fmt=WON)
    R_I9 = R_I0 + len(ITEMS) - 1
    rr2 = R_I9 + 1
    st(ws.cell(row=rr2, column=1, value="※ 목전지는 시즈닝 미적용(두루치기용) — 시즈닝 원가 0"), size=9, color="595959")
    for col in range(2, 11):
        st(ws.cell(row=rr2, column=col), size=9)

    # ── 판단 메모 ───────────────────────────────────────────────────
    r = rr2 + 2
    section(ws, r, "[8] 검토 포인트")
    notes = [
        "0) [2] 블록은 가루 배합 전제다. 2026-08-12 2차 통화에서 가루형이 배제되고 액상 2안(분무기 도포·염지액 충진)으로",
        "   좁혀졌으므로, 액상 방식이 확정되면 원료 구성과 투입률을 다시 잡아야 한다.",
        "1) 수율이 미확인이다. 95% 가정이며, 90%면 원물원가가 kg당 약 400원 오른다. 정담에 반드시 확인할 것.",
        "2) 시즈닝 원료 3종의 포장단가가 비어 있다. 채우기 전까지 역산 가공비는 과대 표시된다.",
        "3) 면세 → 과세 전환이 확정적이다. 점주가 일반과세자면 실부담은 없으나, 메뉴 코스트를 부가세 포함으로",
        "   잡는 구조라 원가율이 올라 보인다. 점주 설득 비용으로 봐야 한다.",
        "4) 정담 원안은 원물 7,200원 전제의 9,600원이다. 당사 실제 원물 구매가 6,900원을 넣고 가공 부가분",
        "   2,400원을 그대로 얹어 9,300원으로 재산출했다. 정담에 이 단가로 확인을 받아야 확정된다.",
        "5) 액상 염지 원가는 정담이 별도 반영하기로 했다(08-12). 회신 오면 [3]에 별도 행으로 추가할 것.",
        "6) 9,600원이 원물 포함가인지 작업비만인지 불명확하다. 자사 질의는 원재료비 배제 기준이었으나 정담은",
        "   원물가 7,200원을 전제로 답했다. 작업비만 9,600원이면 원물보다 비싸 성립하지 않아 원물 포함으로 가정했다.",
        "7) 텀블링 불가(정담 텀블러 미보유) — 수작업 도포로 진행한다. 도포 균일도가 테스트에서 문제되면",
        "   설비 보유 업체를 다시 봐야 하며, 그 경우 이 단가는 무효가 된다.",
    ]
    for i, t in enumerate(notes):
        c = ws.cell(row=r + 1 + i, column=1, value=t)
        c.font = Font(name=F, size=9, color=RED if i in (0, 1, 2, 7) else "1a1a1a")
        c.alignment = Alignment(horizontal="left", vertical="center")

    ws.freeze_panes = "A4"

    # ── 참고 시트 ───────────────────────────────────────────────────
    ws2 = wb.create_sheet("품목현황")
    ws2.sheet_view.showGridLines = False
    c = ws2.cell(row=1, column=1, value="대상 6종 현황 (품목리스트 2026-08-12 기준)")
    c.font = Font(name=F, bold=True, size=13, color=NAVY)
    head(ws2, 3, ["품목", "원산지 / 브랜드", "세절 규격", "보관", "매입가", "공급가", "마진율", "월사용량(1개점)", "시즈닝", "비고"],
         widths=[26, 18, 30, 8, 11, 11, 10, 15, 10, 22])
    spec = [
        ("구이삼겹살", "독일 / 테니시", "2×2cm × 원육길이 다이스", "냉동"),
        ("목살", "캐나다 / 올리멜", "2×1.8cm × 원육길이(1/2) 다이스", "냉동"),
        ("항정살", "스페인 / 프리빈", "7mm 슬라이스", "냉동"),
        ("삼겹양지", "미국 / 엑셀", "2mm 슬라이스", "냉동"),
        ("대패삼겹살", "독일 / 시몬", "5mm 슬라이스 후 3~4등분", "냉동"),
        ("목전지", "미국 / 스미스필드", "2.5mm 슬라이스 6등분", "냉동"),
    ]
    for i, ((nm, buy, sup, qty, seasoned), (snm, og, sp, keep)) in enumerate(zip(ITEMS, spec)):
        rr = 4 + i
        st(ws2.cell(row=rr, column=1, value=snm), b=True, fill=CALC)
        st(ws2.cell(row=rr, column=2, value=og), align="center")
        st(ws2.cell(row=rr, column=3, value=sp), size=9)
        st(ws2.cell(row=rr, column=4, value=keep), align="center")
        st(ws2.cell(row=rr, column=5, value=buy), align="center", fmt=WON)
        st(ws2.cell(row=rr, column=6, value=sup), align="center", fmt=WON)
        st(ws2.cell(row=rr, column=7, value=f"=1-E{rr}/F{rr}"), align="center", fmt=PCT)
        st(ws2.cell(row=rr, column=8, value=qty), align="center", fmt=WON)
        st(ws2.cell(row=rr, column=9, value="적용" if seasoned else "미적용"), align="center")
        st(ws2.cell(row=rr, column=10, value="" if seasoned else "두루치기용 원물 납품"), size=9, color="595959")
    rr = 4 + len(ITEMS)
    st(ws2.cell(row=rr, column=1, value="합계"), b=True, fill=SUB)
    for col in range(2, 8):
        st(ws2.cell(row=rr, column=col), fill=SUB)
    st(ws2.cell(row=rr, column=8, value=f"=SUM(H4:H{rr-1})"), b=True, align="center", fmt=WON, fill=SUB)
    for col in (9, 10):
        st(ws2.cell(row=rr, column=col), fill=SUB)

    ws2.cell(row=rr + 2, column=1,
             value="※ 월사용량은 입고량 기준이라 실사용량보다 과대 가능. 재고 대사 후 확정 필요.").font = \
        Font(name=F, size=9, color=RED)

    wb.save(path)
    print("saved:", path)


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    out = sys.argv[1] if len(sys.argv) > 1 else "20260812_육직구_시즈닝_단가검토.xlsx"
    build(out if os.path.isabs(out) else os.path.join(base, out))
