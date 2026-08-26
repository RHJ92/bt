# -*- coding: utf-8 -*-
"""매입마감 대상 시트: ① 결제일 열 신설(매입사_관리 결제유형 매핑) ② 누락 매입사 하단 추가"""
import openpyxl, csv, io, os, re
from copy import copy

BASE = r"c:\Users\BLUETREND\류호정\bt\memo\지출결의서_자동입력"
SHEET = os.path.join(BASE, '팀장님이 만드신 매입마감 대상.xlsx')
MGMT = os.path.join(BASE, 'raw', '매입사_관리 3120220fdfc280c1b110d5739eb7bad1_all.csv')

mgmt = []
for r in csv.DictReader(open(MGMT, encoding='utf-8-sig')):
    mm = sorted(set(re.findall(r'(20\d\d-\d\d)', r['매입사마감_월별강화'] or '')))
    mgmt.append({'name': r['매입사명'].strip(), 'pay': r['결제유형'].strip(),
                 'mm': mm, 'last': mm[-1] if mm else '', 'amt': round(float(r['누적매입금액'] or 0))})
byname = {m['name']: m for m in mgmt}

ALIAS = {'IC푸드': '아이씨푸드', '국순당(자연그대로농업주시회사)': '자연그대로성남공장(국순당)',
         '삼정식품/좋은에프앤비': '삼정식품(좋은에프앤비)', '선호식품': '선호식품(미창f&d)',
         '신우미트(선우프레시)': '신우미트앤푸드', '신우미트(캐틀팜, 케이팩토리)': '신우미트앤푸드',
         '신우미트(캐틀팜,케이팩토리)': '신우미트앤푸드', '제주웰빙푸드': '제주웰빙영농조합',
         '평중-담터': '평중(담터)', '푸미푸드': '푸미식품', '올맘': '올맘(식혜)',
         '해뜨는공장': '해뜨는공장(퍼플블라썸)', '캐틀팜, 케이팩토리': '캐틀팜'}

wb = openpyxl.load_workbook(SHEET)
ws = wb['Sheet1']
HDR, FIRST, LAST = 7, 8, 57
PAY_COL = 15                      # O열 = 결제일 (비고 N열 뒤)

# ── ① 결제일 열 신설 ────────────────────────────────────────
h = ws.cell(HDR, PAY_COL)
h.value = '결제일'
h._style = copy(ws.cell(HDR, 14)._style)
ws.column_dimensions['O'].width = 16

used = set()
for i in range(FIRST, LAST + 1):
    name = (ws.cell(i, 1).value or '').strip()
    if not name: continue
    c = ws.cell(i, PAY_COL)
    c._style = copy(ws.cell(i, 14)._style)
    m = byname.get(ALIAS.get(name, name))
    if m:
        c.value = m['pay']
        used.add(m['name'])
        if name == '캐틀팜, 케이팩토리':
            used.add('케이팩토리(캐틀팜지사)')

# ── ② 누락 매입사 하단 추가 ────────────────────────────────
miss = [m for m in mgmt if m['name'] not in used and m['mm']]
miss.sort(key=lambda m: (m['last'], m['amt']), reverse=True)

row = LAST + 1
for m in miss:
    for col in range(1, PAY_COL + 1):
        ws.cell(row, col)._style = copy(ws.cell(FIRST, min(col, 14))._style)
    ws.cell(row, 1).value = m['name']
    ws.cell(row, 14).value = f"매입사_관리 등록 · 8월 발주 미집계 (최근마감 {m['last']})"
    ws.cell(row, PAY_COL).value = m['pay']
    row += 1

wb.save(SHEET)
print(f"결제일 매핑 {len(used)}곳 / 추가 {len(miss)}행 (행 {LAST+1}~{row-1})")
