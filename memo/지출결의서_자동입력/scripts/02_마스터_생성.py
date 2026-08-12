# -*- coding: utf-8 -*-
"""개발팀 전달용 마스터 생성 — 2026-05~08 이체요청일 기준"""
import csv, os, re, collections
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE = r"c:\Users\BLUETREND\류호정\bt\memo\지출결의서_자동입력"
RAW = os.path.join(BASE, 'raw')

# ── 로우 로드 ────────────────────────────────────────────────
DEPT = '구매공급관리팀'
with open(os.path.join(RAW, '필터_2026_05-08_지출결의서.csv'), encoding='utf-8-sig', newline='') as fh:
    ALL = list(csv.DictReader(fh))
for r in ALL:
    r['지출부서(팀)'] = r['지출부서(팀)'].strip()
    r['승인자'] = r['승인자'].strip()
R = [r for r in ALL if r['지출부서(팀)'] == DEPT]
with open(os.path.join(RAW, f'필터_2026_05-08_{DEPT}.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(ALL[0].keys()))
    w.writeheader(); w.writerows(R)

wb_i = openpyxl.load_workbook(os.path.join(RAW, '품목별 제조사.xlsx'), data_only=True)
ws_i = wb_i.worksheets[0]
irows = list(ws_i.iter_rows(values_only=True))
ihdr = [str(c).strip() if c is not None else '' for c in irows[5]]
I_TYPE, I_NAME = ihdr.index('상품유형'), ihdr.index('품명')
I_PAY = ihdr.index('결제일')
IDX_MK = [i for i, h in enumerate(ihdr) if h == '매입사']

def nz(row, i):
    v = row[i] if i < len(row) else None
    return str(v).strip() if v is not None else ''

def norm(s):
    s = (s or '').strip()
    s = re.sub(r'\(주\)|\(유\)|㈜|주식회사|유한회사|유한책임회사|농업회사법인|농협주식회사', '', s)
    s = re.sub(r'[\s\-_/().,]', '', s)
    return s.lower()

# 매입사 문자열 → 후보 이름들 (괄호 안/밖, (제때) 접두, 구분자 분리)
def maker_keys(m):
    ks = set()
    m = m.strip()
    if not m: return ks
    ks.add(m)
    m2 = re.sub(r'^\(제때\)', '', m).strip()
    ks.add(m2)
    inside = re.findall(r'\(([^)]*)\)', m2)
    outside = re.sub(r'\([^)]*\)', '', m2).strip()
    if outside: ks.add(outside)
    for chunk in inside:
        for t in re.split(r'[,/]', chunk):
            if t.strip(): ks.add(t.strip())
    for t in re.split(r'[/]', outside):
        if t.strip(): ks.add(t.strip())
    return {k for k in ks if k and k not in ('유동적', '자제생산', '각 물류사 범용')}

MAKER_TYPE = collections.defaultdict(collections.Counter)   # normkey -> 상품유형
MAKER_PAY  = collections.defaultdict(collections.Counter)   # normkey -> 결제일
for row in irows[6:]:
    if not nz(row, I_NAME): continue
    t, pay = nz(row, I_TYPE), nz(row, I_PAY)
    for i in IDX_MK:
        for k in maker_keys(nz(row, i)):
            if t:   MAKER_TYPE[norm(k)][t] += 1
            if pay: MAKER_PAY[norm(k)][pay] += 1

# ── 별칭 병합 (수기 커레이션) ───────────────────────────────
MERGE = {
    '강서푸드뱅크(깍두기)': '강서푸드뱅크',
    'swc': 'SWC',
    'Skn테크노파크': 'SKn테크노파크',
    '(주)삼보종합물류 평택지점': '삼보종합물류 평택지점',
    '꾸러기 수비대': '꾸러기수비대', '(주)꾸러기수비대': '꾸러기수비대',
    '감천부두냉동공장 고려냉장': '고려냉장(감천부두냉동공장)', '고려냉장': '고려냉장(감천부두냉동공장)',
    '노마진(코리아)': '노마진코리아',
    '[디자인제작] 성원애드피아 디자인물 발주': '성원애드피아',
    '[디자인제작] 애드피아몰 디자인물 발주': '애드피아몰',
    '[디자인제작] 바우상사 디자인물 4월 발주': '바우상사',
    '[개인경비]남궁민 개인경비 지출(유류비,통행료)': '남궁민',
    '(주)삼성건물관리': '삼성건물관리', '삼성건물관리_아이페리온': '삼성건물관리',
    '오로CS': '오로라CS', '오로라cs': '오로라CS',
    '제주웰빙영농조합': '제주웰빙영농조합법인(용인지사)', '제주웰빙영농조합법인': '제주웰빙영농조합법인(용인지사)',
    '케이엠에스': '케이엠에스패밀리',
    '카페24주식회사': '카페24',
    '김흥곤': '김홍곤',
    '주식회사 인디엠': '인디엠',
    '정백선': '정백선에프엔비', '옥된장F&B': '옥된장 에프엔비(내부)', '옥된장 에프엔비': '옥된장 에프엔비(내부)',
    '평중-담터': '평중',
    '박귀자 외 1곳': '박귀자 외 1명',
    '월드로얄패밀리': '월드로얄패밀리 주식회사',
    '정백선순대 판교역점': '정백선순대 판교점',
    '(주)월드전람': '월드전람',
    '㈜브이웍스': '브이웍스',
    '(주)씨제이이엔앰': '씨제이이엔엠',
    '(주)사인버스': '사인버스',
    '부산항운노동조합(삼일냉장 노조반)': '부산항운노동조합 삼일냉장 노조반',
    '부산항운노동조합 삼일냉장 제1물류센터 노조반': '부산항운노동조합 삼일냉장 노조반',
}
# 경조사비 — 사내 지정계좌 1개로 수렴
GYEONGJO = ['[접대비] 故정기봉 부의금(송평기)', '[접대비] 김상연 축의금', '[접대비] 김재성 축의금',
            '[접대비] 김지현 축의금', '김민정 축의금(김시형)', '김영현 축의금', '김재훈', '방세잎', '조민곤']
for g in GYEONGJO:
    MERGE[g] = '경조사비(사내 지정계좌)'
# 원천세 — 거래처가 아니라 세목
WONCHEON = ['성남세무서, 수정구청', '수정구청, 성남세무서', '성남세무서, 중원구청', '중원구청, 성남세무서']
for w in WONCHEON:
    MERGE[w] = '원천세(관할 세무서·구청)'
EXCLUDE = {'테스트', '1', '거래처명'}

# ── 카테고리 표준값 사전 ────────────────────────────────────
CAT_MAP = {
    # 상품
    '김치류': '절임류', '콩국물': '공산품', '면류': '공산품', '수제비': '공산품', '만두': '공산품',
    '기타가공품': '공산품', '가공김': '공산품', '농산가공품': '공산품',
    '건표고버섯': '농산품',
    '축산': '축산품', '축산물': '축산품', '축산가공품': '가공축산',
    '수산가공품': '수산품', '냉동수산물, 냉동야채': '수산품', '냉동수산물,냉동야채': '수산품',
    '[축산품(계란)]': '축산품(계란)', '계란': '축산품(계란)',
    '육수베이스': '원재료', '전파우더': '원재료', '샘플': '원재료',
    '물티슈': '부자재', '쇼핑백': '부자재', '소모품': '부자재', '비품': '부자재',
    '포장비': '하역비',   # 자숙문어 출고 시 적재·상하차·랩포장 작업비 → 하역비
    '상품': '상품(판촉물)',
    # 물류·창고
    '창고': '창고비', '보관비': '창고비', '운임비': '운송비', '배송비': '운송비', '출고비': '하역비',
    # 광고
    '가맹 광고': '가맹광고', '브랜드 광고': '브랜드광고', '브랜딩광고': '브랜드광고',
    'LSM, LSM기존지원': 'LSM 기존지원',
    # 임직원
    '개인 경비': '개인경비', '개인경비_브랜드광고': '개인경비(브랜드광고)',
    '개인경비(브랜드광고)': '개인경비(브랜드광고)',
    # 기타
    '[이자]': '이자', '임대료+관리비': '임대료·관리비', '임대료, 관리비': '임대료·관리비',
    '수수료 차액': '수수료',
}
CAT_DROP = {'테스트', '1', '지출 카테고리', '제때', ''}

def std_cat(c):
    c = (c or '').strip()
    if c in CAT_DROP: return ''
    return CAT_MAP.get(c, c)

GUBUN = [
    ('상품매입', {'공산품','농산품','축산품','수산품','소스류','절임류','음료','축산품(계란)','가공축산','원재료','부자재','식기류','상품(판촉물)'}),
    ('물류·창고', {'운송비','창고비','파렛트','하역비'}),
    ('광고·마케팅', {'가맹광고','브랜드광고','LSM','LSM 기존지원','디자인제작','박람회'}),
    ('세금·공과', {'세금','보증료'}),
    ('내부거래·금융', {'내부거래','이자','투자주식','차입금','고정자산'}),
    ('임직원·경조사', {'개인경비','개인경비(브랜드광고)','접대비','복리비','주차비 지원','인건비'}),
    ('가맹점', {'가맹해지','반환','지원','교육비'}),
]
# 자사 법인 — 상품 매입이 아니라 내부거래. 단 블루푸드랩은 구매팀이 소스를 매입하는 대상이라 제외
INTERNAL = {'블루트렌드', '옥된장 에프엔비(내부)', '정백선에프엔비', '철산장에프엔비',
            '영영애드', '정백선순대 광교점', '정백선순대 판교점'}

def gubun(cat, name):
    if name in INTERNAL: return '내부거래·금융'
    if re.match(r'^(옥된장|석문어|정백선순대|철산장|영영상점)\s', name or ''): return '가맹점'
    for g, s in GUBUN:
        if cat in s: return g
    return '용역·수수료'

# ── 계좌 문자열 3분할 ───────────────────────────────────────
BANK_RE = re.compile(
    r'^\s*(KB국민은행|국민은행|IBK기업은행|기업은행|신한은행|우리은행|하나은행|농협은행|경남은행|부산은행|'
    r'카카오뱅크|토스뱅크|수협은행|새마을금고|우체국|수협|신협|국민|기업|신한|우리|하나|농협|KB|IBK|NH)')
NUM_RE = re.compile(r'\d[\d\s\-]{5,}\d')
NOACC = ('본문에 내용 작성', '본문에 첨부 예정', '별첨', '테스트', '1', '은행 및 계좌정보 (혼선방지)')

def split_acct(s):
    s = re.sub(r'\s+', ' ', (s or '').strip())
    if not s or s in NOACC:
        return '', '', '', s
    m = BANK_RE.match(s)
    bank = m.group(1) if m else ''
    rest = s[m.end():] if m else s
    mn = NUM_RE.search(rest)
    if not mn:
        return bank, '', rest.strip(' /'), ''
    num = mn.group(0).strip()
    holder = (rest[:mn.start()] + ' ' + rest[mn.end():]).strip(' /')
    holder = re.sub(r'\s+', ' ', holder).strip(' /')
    return bank, num, holder, ''

def acctnum(s): return re.sub(r'\D', '', s or '')

# ── 거래처 집계 ─────────────────────────────────────────────
groups = collections.defaultdict(list)
for r in R:
    v = r['거래처명(확정)'].strip()
    if v in EXCLUDE: continue
    groups[MERGE.get(v, v)].append(r)

def mode_of(rows, col, std=None):
    c = collections.Counter()
    for r in rows:
        v = (r[col] or '').strip()
        if std: v = std(v)
        if v: c[v] += 1
    return (c.most_common(1)[0][0] if c else ''), c

def content_template(rows):
    conts = [(r['지출내용'] or r['지출내용(제목)'] or '').strip() for r in rows]
    conts = [c for c in conts if c]
    if not conts: return ''
    gen = [re.sub(r'\d{1,2}\s*월', '{월}월', re.sub(r'^\d{2,4}[.\-년]\s*', '', c)) for c in conts]
    c = collections.Counter(gen)
    top, n = c.most_common(1)[0]
    if n >= 2 and len(top) <= 30: return top
    return conts[-1][:30]

def paycond(name):
    c = MAKER_PAY.get(norm(name))
    if not c: return ''
    return ' / '.join(k for k, _ in c.most_common(2))

rows_out = []
for name, rows in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])):
    aliases = sorted({r['거래처명(확정)'].strip() for r in rows} - {name})
    법인, c법 = mode_of(rows, '지출법인')
    부서, c부 = mode_of(rows, '지출부서(팀)')
    속성, c속 = mode_of(rows, '거래속성')

    cats = collections.Counter()
    for r in rows:
        v = std_cat(r['지출 카테고리'] or r['카테고리(제목)'])
        if v: cats[v] += 1
    itype = None if name in INTERNAL else MAKER_TYPE.get(norm(name))
    if itype:
        t = itype.most_common(1)[0][0]
        t = {'계란': '축산품(계란)', '축산가공품': '가공축산'}.get(t, t)
        cat, src = t, '품목별 제조사(상품유형)'
        if cats and cats.most_common(1)[0][0] != cat:
            src += f" ※실적최빈={cats.most_common(1)[0][0]}"
    else:
        cat = cats.most_common(1)[0][0] if cats else ''
        src = '5~8월 실적 최빈값' if cat else '(근거없음)'

    accs = collections.Counter()
    for r in rows:
        a = (r['은행/계좌번호/예금주'] or '').strip()
        if a: accs[a] += 1
    main = re.sub(r'\s+', ' ', accs.most_common(1)[0][0]) if accs else ''
    memo = main if main in NOACC else ''
    if memo:
        main = ''
    else:
        # 한 칸에 담되 「은행 계좌번호 예금주」 형태로 표기 통일 (구분자·띄어쓰기 제각각 정리)
        bk, nm, hd, _ = split_acct(main)
        if bk and nm:
            main = ' '.join(x for x in (bk, nm, hd) if x)
    uniq = {acctnum(a) for a in accs if acctnum(a)}

    flags = []
    if len(c법) > 1: flags.append(f"법인 {len(c법)}종({'/'.join(c법)})")
    if len(c부) > 1: flags.append(f"부서 {len(c부)}종")
    if len(uniq) > 1: flags.append(f"계좌 {len(uniq)}개")
    if not uniq: flags.append('계좌 미기재')
    if len(cats) > 1: flags.append(f"카테고리 {len(cats)}종({'/'.join(cats)})")
    if not cat: flags.append('카테고리 없음')
    if acctnum(main) in ('27120104295948', '100037925755') and '블루트렌드' not in name:
        flags.append('자사 계좌 기재 — 오기 의심')

    last = max(r['이체요청일'] for r in rows)
    rows_out.append({
        '표준거래처명': name,
        '별칭(과거 표기)': ' | '.join(aliases),
        '거래처구분': gubun(cat, name),
        '지출카테고리(기본값)': cat,
        '카테고리 근거': src,
        '지출법인(기본값)': 법인,
        '지출부서(기본값)': 부서,
        '거래속성': 속성,
        '은행/계좌번호/예금주': main,
        '계좌 비고': memo or ('복수계좌' if len(uniq) > 1 else ''),
        '결제조건': paycond(name),
        '지출내용 템플릿': content_template(rows),
        '5~8월 건수': len(rows),
        '최근 이체요청일': last,
        '검토필요': ' / '.join(flags),
    })

# ── 결재선 ──────────────────────────────────────────────────
appr = collections.defaultdict(lambda: {'승': collections.Counter(), '결': collections.Counter(), 'n': 0})
for r in R:
    k = (r['지출법인'].strip(), r['지출부서(팀)'].strip())
    if not k[0]: continue
    a = appr[k]; a['n'] += 1
    if r['승인자'].strip(): a['승'][r['승인자'].strip()] += 1
    if r['결제자'].strip(): a['결'][r['결제자'].strip()] += 1

PAYER_BY_CORP = {'블루트렌드': '정준선', '철산장 에프엔비': '정준선', '영영애드': '정준선',
                 '옥된장 에프엔비': '민선아', '석문어 에프엔비': '민선아',
                 '정백선 에프엔비': '민선아', '블루푸드랩(영영키친)': '민선아'}
FIXED_APPROVER = {'구매공급관리팀': '김민혁'}

appr_rows = []
for (corp, dept), a in sorted(appr.items(), key=lambda x: -x[1]['n']):
    seung = collections.Counter({k.strip(): v for k, v in a['승'].items()})
    rec_a = FIXED_APPROVER.get(dept) or (seung.most_common(1)[0][0] if seung else '')
    rec_p = PAYER_BY_CORP.get(corp) or (a['결'].most_common(1)[0][0] if a['결'] else '')
    note = []
    if dept in FIXED_APPROVER: note.append('구매공급관리팀 승인자 = 김민혁 고정')
    if len(seung) > 2 and dept not in FIXED_APPROVER: note.append('승인자 분산 — 확정 필요')
    appr_rows.append([corp, dept, rec_a, rec_p, a['n'],
                      ', '.join(f"{k}({v})" for k, v in seung.most_common()),
                      ', '.join(f"{k}({v})" for k, v in a['결'].most_common()),
                      ' / '.join(note)])

# ── 카테고리 표준값 시트 ────────────────────────────────────
raw_cats = collections.Counter()
for r in R:
    raw_cats[(r['지출 카테고리'] or r['카테고리(제목)'] or '').strip()] += 1
cat_rows = []
for old, n in raw_cats.most_common():
    if old in CAT_DROP and old != '':
        cat_rows.append([old, '(사용중지)', n, '오입력·테스트값'])
        continue
    if not old:
        cat_rows.append(['(공란)', '(입력필수)', n, '제목에도 카테고리 없음'])
        continue
    new = std_cat(old)
    cat_rows.append([old, new, n, '통합' if new != old else ''])

STD_LIST = sorted({std_cat(o) for o in raw_cats if std_cat(o)})

# ── 엑셀 쓰기 ───────────────────────────────────────────────
wb = openpyxl.Workbook()
H = PatternFill('solid', fgColor='1F3864')
HF = Font(color='FFFFFF', bold=True, size=10)
BD = Border(*[Side('thin', color='BFBFBF')] * 4)

def sheet(title, headers, data, widths):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for c in ws[1]:
        c.fill, c.font, c.border = H, HF, BD
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    for row in data:
        ws.append(row)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.border = BD
            c.alignment = Alignment(vertical='center', wrap_text=True)
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    return ws

ws0 = wb.active; ws0.title = '00_읽어주세요'
intro = [
    ['지출결의서 자동입력 — 개발팀 전달 자료'],
    [''],
    ['목적', '지출결의서 작성 시 「거래처명」 하나만 선택하면 나머지 항목이 자동으로 채워지도록 개선'],
    ['대상', f'지출부서 = {DEPT} / 2026년 5~8월 (이체요청일 기준) {len(R)}건 / 거래처 {len(rows_out)}곳'],
    ['원본', '노션 「지출 결의서 Master DB」 4,166건 중 기간 필터 / 「품목별 제조사」 엑셀 383품목'],
    [''],
    ['시트 구성'],
    ['01_거래처마스터', '거래처명 → 자동으로 불러올 값. 이 표가 본체'],
    ['02_카테고리_표준값', '지출 카테고리 값을 통합한 사전. select 박스 값 목록으로 사용'],
    ['03_결재선', '승인자·결제자는 거래처가 아니라 (법인 × 부서)로 결정됨. 별도 테이블로 분리'],
    ['04_확인필요', '값이 충돌해 자동입력 전 사람 확인이 필요한 건'],
    [''],
    ['설계 요청'],
    ['1', '거래처명은 자유 입력이 아니라 마스터에서 선택. 별칭 컬럼의 과거 표기로도 검색되게 할 것'],
    ['2', '자동 채움 항목: 지출카테고리 / 지출법인 / 지출부서 / 거래속성 / 은행·계좌번호·예금주'],
    ['3', '지출법인은 기본값만 제시하고 사용자가 변경 가능해야 함 (한 매입처를 여러 법인이 사용)'],
    ['4', '계좌는 현행대로 「은행 계좌번호 예금주」 한 칸에 담되, 표기 형식은 이 표의 값으로 통일'],
    ['5', '거래처가 계좌를 여러 개 쓰는 경우 선택형(라디오)으로 제공 — 04 시트 참고'],
    ['6', '승인자·결제자는 거래처가 아니라 로그인 사용자의 부서·법인에서 결정 (03 시트). '
          '구매공급관리팀 승인자는 김민혁 고정, 결제자는 법인으로 갈림'],
    ['7', '제목은 「[지출카테고리]거래처명_지출내용」 자동 조합. 실적 96%가 이 규칙을 따름 — 수기 입력 제거 가능'],
    ['8', '지출내용·지출목적·금액·이체요청일은 건별로 달라 자동입력 대상 아님. 템플릿 문구만 제안'],
    [''],
    ['참고', '2025년 1~9월에 노션 릴레이션으로 거래처명·계좌번호 자동 불러오기를 운영한 이력이 있음'],
    ['', '(「[종료] 거래처명(불러오기)」 컬럼 1,046건). 중단 사유를 먼저 확인할 것'],
]
for r in intro: ws0.append(r)
ws0['A1'].font = Font(bold=True, size=14)
for r in (7, 13): ws0.cell(row=r, column=1).font = Font(bold=True)
ws0.column_dimensions['A'].width = 18
ws0.column_dimensions['B'].width = 105
for row in ws0.iter_rows():
    for c in row: c.alignment = Alignment(vertical='center', wrap_text=True)

cols = ['표준거래처명','별칭(과거 표기)','거래처구분','지출카테고리(기본값)','카테고리 근거','지출법인(기본값)',
        '지출부서(기본값)','거래속성','은행/계좌번호/예금주','계좌 비고','결제조건','지출내용 템플릿',
        '5~8월 건수','최근 이체요청일','검토필요']
sheet('01_거래처마스터', cols, [[r[c] for c in cols] for r in rows_out],
      [26,34,13,16,24,16,16,18,46,12,16,26,10,14,34])

sheet('02_카테고리_표준값', ['기존 입력값','표준값','5~8월 건수','비고'], cat_rows, [26,20,12,26])
ws2 = wb['02_카테고리_표준값']
ws2.append([]); ws2.append(['표준값 목록 (select 박스용)']); ws2.cell(ws2.max_row, 1).font = Font(bold=True)
for s in STD_LIST: ws2.append([s])

sheet('03_결재선', ['지출법인','지출부서(팀)','승인자(권장)','결제자(권장)','5~8월 건수','승인자 실적','결제자 실적','비고'],
      appr_rows, [20,20,14,14,12,34,26,30])

chk = [[r['표준거래처명'], r['검토필요'], r['별칭(과거 표기)'], r['5~8월 건수']] for r in rows_out if r['검토필요']]
sheet('04_확인필요', ['표준거래처명','확인 사유','별칭','건수'], chk, [26,52,34,10])

path = os.path.join(BASE, f'개발팀_전달_지출결의서_거래처마스터_{DEPT}_2026.05-08.xlsx')
wb.save(path)
print('saved', path, '| 거래처', len(rows_out), '| 확인필요', len(chk), '| 카테고리 표준값', len(STD_LIST))
