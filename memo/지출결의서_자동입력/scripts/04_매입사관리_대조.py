# -*- coding: utf-8 -*-
"""매입사_관리 DB vs 전달본 거래처마스터 — 누락 점검 (양방향 별칭·부분일치)"""
import csv, io, os, re
import openpyxl

BASE = r"c:\Users\BLUETREND\류호정\bt\memo\지출결의서_자동입력"
RAW = os.path.join(BASE, 'raw')
out = io.StringIO()
def p(*a): print(*a, file=out)

M = list(csv.DictReader(open(os.path.join(RAW, '매입사_관리 3120220fdfc280c1b110d5739eb7bad1_all.csv'),
                            encoding='utf-8-sig')))
wb = openpyxl.load_workbook(os.path.join(BASE, '인사총무팀_전달_지출결의서_거래처마스터_260811.xlsx'))
ws = wb['01_거래처마스터']
h = {c.value: i for i, c in enumerate(ws[1])}
MASTER = [r[h['표준거래처명']].strip() for r in ws.iter_rows(min_row=2, values_only=True) if r[h['표준거래처명']]]

DROP = ('주식회사','유한회사','유한책임회사','농업회사법인','(주)','(유)','㈜','종료','중단','지사','지점','공장','창고')
def norm(s):
    s = (s or '').strip()
    for d in DROP: s = s.replace(d, '')
    return re.sub(r'[\s\-_/().,&]', '', s).lower()

def keys(name):
    ks = {name}
    inside = re.findall(r'\(([^)]*)\)', name)
    outside = re.sub(r'\([^)]*\)', '', name).strip()
    if outside: ks.add(outside)
    ks |= {t.strip() for t in inside if t.strip()}
    return {norm(k) for k in ks if norm(k)}

MK = [(m, keys(m)) for m in MASTER]

def match(name):
    nk = keys(name)
    for m, mk in MK:                      # 완전 일치
        if nk & mk: return m, '일치'
    for m, mk in MK:                      # 부분 포함
        for a in nk:
            for b in mk:
                if len(a) >= 3 and len(b) >= 3 and (a in b or b in a):
                    return m, '유사'
    return '', ''

rows = []
for r in M:
    name = r['매입사명'].strip()
    mm = sorted(set(re.findall(r'(20\d\d-\d\d)', r['매입사마감_월별강화'] or '')))
    hit, kind = match(name)
    rows.append({'name': name, 'pay': r['결제유형'].strip(), 'gubun': r['구분'].strip(),
                 'amt': round(float(r['누적매입금액'] or 0)), 'mm': mm,
                 'last': mm[-1] if mm else '', 'hit': hit, 'kind': kind})

live = [r for r in rows if r['mm']]
p(f"매입사_관리 {len(rows)}곳 / 마감이력 있음 {len(live)}곳 / 전달본 마스터 {len(MASTER)}곳")
p("마감이력 없음(제외 대상) 8곳:", ', '.join(r['name'] for r in rows if not r['mm']))
p()

def fmt(r):
    return (f"{r['name']} | 최근마감 {r['last']} ({len(r['mm'])}건) | 결제 {r['pay']} | "
            f"구분 {r['gubun'] or '-'} | 누적 {r['amt']:,}원"
            + (f" | 마스터 '{r['hit']}' 와 유사" if r['kind'] == '유사' else ''))

sim = [r for r in live if r['kind'] == '유사']
mis = [r for r in live if not r['kind']]
p(f"■ 일치 {sum(1 for r in live if r['kind']=='일치')} / 유사(확인) {len(sim)} / 누락 {len(mis)}")
p()
p("── 유사 — 같은 곳인지 확인 필요")
for r in sorted(sim, key=lambda x: x['last'], reverse=True): p("  ", fmt(r))
p()
for label, cond in [('A. 2026-05 이후 거래 있음 — 추가 검토 1순위', lambda r: r['last'] >= '2026-05'),
                    ('B. 2026-01~04 거래만 — 5~8월에 없어 빠진 곳', lambda r: '2026-01' <= r['last'] < '2026-05'),
                    ('C. 그 외', lambda r: r['last'] < '2026-01')]:
    sel = [r for r in mis if cond(r)]
    if not sel: continue
    p(f"── 누락 {label} ({len(sel)}곳)")
    for r in sorted(sel, key=lambda x: (x['last'], x['amt']), reverse=True): p("  ", fmt(r))
    p()

open(os.path.join(r"C:\Users\BLUETR~1\AppData\Local\Temp\claude\c--Users-BLUETREND-----bt\494acd7a-9e99-48d6-a8ae-95be5ee16280\scratchpad", 'gap2.md'),
     'w', encoding='utf-8').write(out.getvalue())
print('done')
