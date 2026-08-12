# -*- coding: utf-8 -*-
"""1단계: 2026-05~08 이체요청일 기준 지출결의서 필터링 + 품목별제조사 상품유형 매핑 추출"""
import csv, io, os, re, collections
import openpyxl

RAW = r"c:\Users\BLUETREND\류호정\bt\memo\지출결의서_자동입력\raw"
SP  = r"C:\Users\BLUETR~1\AppData\Local\Temp\claude\c--Users-BLUETREND-----bt\494acd7a-9e99-48d6-a8ae-95be5ee16280\scratchpad"
exp = os.path.join(RAW, "지출 결의서 Master DB 466706fc9e2a461a9d993b919651235d_all.csv")
xls = os.path.join(RAW, "품목별 제조사.xlsx")

out = io.StringIO()
def p(*a): print(*a, file=out)

with open(exp, encoding='utf-8-sig', newline='') as fh:
    E = list(csv.DictReader(fh))

def ymd(s):
    m = re.match(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', s or '')
    if not m: return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

sel = []
for r in E:
    d = ymd(r.get('이체요청일'))
    if d and d[0] == 2026 and 5 <= d[1] <= 8:
        r['_ym'] = f"{d[0]}-{d[1]:02d}"
        sel.append(r)

p("### 2026-05~08 이체요청일 필터")
p("전체", len(E), "→ 대상", len(sel))
for k, n in sorted(collections.Counter(r['_ym'] for r in sel).items()):
    p(f"   {k}: {n}건")
p()

# 제목에서 거래처명 복원
def parse_title(t):
    t = (t or '').strip()
    m = re.match(r'^\[([^\]]+)\]\s*(.+?)_(.+)$', t)
    if m: return m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    m = re.match(r'^(.+?)_(.+)$', t)
    if m: return '', m.group(1).strip(), m.group(2).strip()
    return '', t, ''

got = 0; recovered = 0; none = 0
for r in sel:
    v = (r.get('거래처명') or '').strip()
    cat, tv, cont = parse_title(r.get('이름'))
    r['_cat_title'] = cat
    r['_cont_title'] = cont
    if v:
        r['_vendor'] = v; r['_src'] = '필드'; got += 1
    elif tv:
        r['_vendor'] = tv; r['_src'] = '제목복원'; recovered += 1
    else:
        r['_vendor'] = ''; r['_src'] = '없음'; none += 1
p(f"거래처명 출처 — 필드 {got} / 제목복원 {recovered} / 실패 {none}")

vend = collections.Counter(r['_vendor'] for r in sel if r['_vendor'])
p("고유 거래처 수:", len(vend))
p("건수 상위 25:", vend.most_common(25))
p()

# 품목별 제조사 시트
wb = openpyxl.load_workbook(xls, data_only=True)
ws = wb.worksheets[0]
rows = list(ws.iter_rows(values_only=True))
hdr = [str(c).strip() if c is not None else '' for c in rows[5]]
p("### 품목별 제조사 헤더")
p([(i, h) for i, h in enumerate(hdr) if h])
data = rows[6:]
def cell(row, i):
    v = row[i] if i < len(row) else None
    return str(v).strip() if v is not None else ''

I_TYPE = hdr.index('상품유형')
I_BRAND = hdr.index('브랜드')
I_NAME = hdr.index('품명')
idx_maker = [i for i, h in enumerate(hdr) if h == '매입사']
p("매입사 컬럼 인덱스:", idx_maker, "/ 상품유형", I_TYPE)
p()

recs = []
for row in data:
    nm = cell(row, I_NAME)
    if not nm: continue
    recs.append({
        '품명': nm,
        '상품유형': cell(row, I_TYPE),
        '브랜드': cell(row, I_BRAND),
        '매입사': cell(row, idx_maker[0]),
        '정산매입사': cell(row, idx_maker[1]) if len(idx_maker) > 1 else '',
        '결제일': cell(row, hdr.index('결제일')) if '결제일' in hdr else '',
    })
p("품목 행수:", len(recs))
p("상품유형 값 분포:")
for k, n in collections.Counter(r['상품유형'] for r in recs).most_common():
    p(f"   {k or '(공백)'}: {n}")
p()

# 매입사 → 상품유형
mk = collections.defaultdict(collections.Counter)
for r in recs:
    for f in ['매입사', '정산매입사']:
        m = r[f]
        if m and r['상품유형']:
            mk[m][r['상품유형']] += 1
p("### 매입사 → 상품유형 (매입사 고유", len(mk), ")")
one = sum(1 for k, c in mk.items() if len(c) == 1)
p(f"단일 유형 {one} / 복수 유형 {len(mk)-one}")
for k, c in sorted(mk.items(), key=lambda x: -sum(x[1].values())):
    p(f"   {k}: {dict(c)}")
p()

# 결제일 정보
pay = collections.defaultdict(collections.Counter)
for r in recs:
    for f in ['매입사', '정산매입사']:
        if r[f] and r['결제일']:
            pay[r[f]][r['결제일']] += 1
p("### 매입사 → 결제일")
for k, c in sorted(pay.items()):
    p(f"   {k}: {dict(c)}")
p()

# 5~8월 거래처 vs 품목별제조사 매입사 매칭
def norm(s):
    s = (s or '').strip()
    s = re.sub(r'\(주\)|주식회사|㈜|\(유\)|농업회사법인', '', s)
    s = re.sub(r'[\s\-_/().]', '', s)
    return s.lower()
mknorm = {}
for k in mk:
    mknorm.setdefault(norm(k), k)
hit = [v for v in vend if norm(v) in mknorm]
p("### 5~8월 거래처 vs 품목별제조사 매입사 매칭")
p(f"거래처 {len(vend)}곳 중 매칭 {len(hit)}곳")
p("매칭:", sorted(hit))
p()
p("미매칭(건수순):", [ (v,n) for v,n in vend.most_common() if norm(v) not in mknorm ])

with open(os.path.join(SP, 'step1.md'), 'w', encoding='utf-8') as fh:
    fh.write(out.getvalue())

# 필터 raw 저장
cols = ['이름','거래처명','_vendor','_src','_cat_title','지출 카테고리','_cont_title','지출내용','지출목적',
        '지출법인','지출부서(팀)','요청자','승인자','결제자','은행/계좌번호/예금주','금액(vat포함)',
        '거래속성','상태','이체요청일','_ym','기안 작성(작성일)','생성 일시']
with open(os.path.join(RAW, '필터_2026_05-08_지출결의서.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['제목','거래처명(필드)','거래처명(확정)','거래처명 출처','카테고리(제목)','지출 카테고리','지출내용(제목)','지출내용','지출목적',
                '지출법인','지출부서(팀)','요청자','승인자','결제자','은행/계좌번호/예금주','금액(vat포함)',
                '거래속성','상태','이체요청일','요청월','기안 작성(작성일)','생성 일시'])
    for r in sorted(sel, key=lambda r: (r['_vendor'], r['이체요청일'])):
        w.writerow([r.get(c, '') for c in cols])

with open(os.path.join(RAW, '품목별제조사_매입사_상품유형.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['매입사','상품유형(빈도순)','결제일','품목수'])
    for k, c in sorted(mk.items(), key=lambda x: -sum(x[1].values())):
        w.writerow([k, ' / '.join(f"{t}({n})" for t, n in c.most_common()),
                    ' / '.join(pay.get(k, {}).keys()), sum(c.values())])
print("done")
