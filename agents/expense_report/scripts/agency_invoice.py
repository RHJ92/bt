# 발행 대행사 계산서(메일 본문 링크 → 조회 화면) 열기 → PNG 캡처 + 화면 글자
# 국세청 보안메일(nts_invoice.py)과 같은 원칙: 받는 법인 사업자번호(entities.json)를 고정 스크립트가 넣는다.
# 「수신확인」「수신승인」「승인」「XML전송」 등 업체로 나가는 버튼은 누르지 않는다 — 조회 화면만 캡처
# 대행사별 여는 법은 SITES. 실제 메일로 검증한 곳만 넣는다 (2026-10-30: 매직빌·팝빌·스마트빌·스마일EDI·로지스빌)
# 이카운트(l.ecount.com)는 링크만으로 조회 화면이 열림 (2026-10-30 (주)정담 메일로 확인 — 수신승인 불필요)

import re

from playwright.sync_api import sync_playwright

from nts_invoice import _ENT

# 이카운트 계정 → 받는 법인 (계산서가 그 법인 앞으로 발행됨)
ACCOUNT_ENTITY = {"발주서수신": "블루트렌드", "옥된장": "옥된장", "철산장": "철산장", "석문어": "석문어", "정백선": "정백선"}


def _magicbill(page, biz):
    page.fill("input[name=actno]", biz)
    page.evaluate("fn_submit()")


def _popbill(page, biz):
    # 번호 칸이 숨은 입력칸이라 포커스 후 키보드로 입력
    page.locator("input[inputmode=numeric]").first.focus()
    page.keyboard.type(biz, delay=40)
    page.get_by_role("button", name="확인").click()
    # 다음에 뜨는 「전자계산서를 확인 하시겠습니까?」(공급자에게 확인 신호)는 누르지 않고 X로 닫음
    page.wait_for_timeout(3000)
    close = page.locator("button[class*=topCloseBtn]")
    for i in range(close.count()):
        if close.nth(i).is_visible():
            close.nth(i).click()


def _smileedi(page, biz):
    page.fill("input[name=inpasswd]", biz)
    page.evaluate("Login()")


def _logisbill(page, biz):
    # 번호 입력칸·계산서 화면이 둘 다 iframe 안에 있다 (2026-11-02 정정 — page 레벨 #input1 은 영영 안 보임)
    fr = _frame_with(page, "#input1")
    fr.fill("#input1", biz)
    fr.click("#btn_search")
    page.wait_for_timeout(6000)
    # 값이 innerText 가 아니라 input 에 들어 있어 parse_agency 가 못 읽는다 → 작성일자·합계금액을 글자로 만들어 돌려줌
    pop = next((f for f in page.frames if "inqTaxView" in f.url), None)
    if pop:
        v = pop.evaluate("()=>{const g=i=>(document.getElementById(i)||{}).value||'';"
                         "return [g('PUBLISH_DATE_input'),g('TOTAL_PAY')||g('SET_MONEY'),"
                         "g('STATE_NAME'),g('NTS_STATE_NAME')].join('|')}")
        d, amt, state, nts = (v.split("|") + ["", "", "", ""])[:4]
        return f"작성일자 {d} 합계금액 {amt} 업무상태 {state} 국세청전송상태 {nts}"


def _frame_with(page, sel, timeout=30000):
    """그 선택자가 있는 프레임(메인 포함) — 로지스빌처럼 화면이 iframe 안에 있는 사이트용"""
    for _ in range(timeout // 500):
        for f in page.frames:
            try:
                if f.query_selector(sel):
                    return f
            except Exception:
                pass
        page.wait_for_timeout(500)
    raise RuntimeError(f"{sel} 가 어느 프레임에도 없음")


def _smartbill(page, biz):
    pass  # 링크만으로 조회 화면이 열림 (수신승인 버튼은 누르지 않음)


def _ecount(page, biz):
    pass  # 링크만으로 조회 화면이 열림 — 「수신승인」은 누르지 않는다


def _wehago(page, biz):
    page.fill("input[placeholder*='없이']", biz)
    _modal_ok(page)
    page.wait_for_timeout(4000)
    if page.get_by_text("첨부문서가 존재").count():  # 첨부 안내창만 닫음
        _modal_ok(page)


def _modal_ok(page):
    """가운데 안내창의 확인만 누름 — 상단의 계산서 「확인」(공급자에게 확인 신호)은 위쪽이라 제외"""
    y, btn = max(((b.bounding_box()["y"], b) for b in page.locator("button:visible", has_text="확인").all()),
                 key=lambda t: t[0])
    if y < 300:
        raise RuntimeError("안내창 확인 버튼을 못 찾음")
    btn.click()


SITES = {
    # 보낸사람 도메인: (본문 링크 패턴, 여는 동작)
    "magicbill.co.kr": (r"https://www\.magicbill\.co\.kr/etax/etax_preview\.do\?[^\"'\s<>]+", _magicbill),
    "popbill.com": (r"https://www\.popbill\.com/App/Taxinvoice/[^\"'\s<>]+", _popbill),
    "smileedi.com": (r"https://www\.smileedi\.com/DtiEmail\.do\?[^\"'\s<>]+", _smileedi),
    "logisbill.co": (r"https://www\.logisbill\.com/swf/EML_Controller\.jsp\?[^\"'\s<>]+", _logisbill),
    "bill36524.com": (r"https://www\.wehago\.com/invoice/#/eTaxMail/[^\"'\s<>]+", _wehago),
    "businesson.co.kr": (r"https://www2\.smartbill\.co\.kr/xDti/n_mem/loginCookieClear\.aspx\?[^\"'\s<>]+", _smartbill),
    "ecount.com": (r"https://l\.ecount\.com/[A-Za-z0-9_-]+", _ecount),  # 링크 토큰에 _ 가 섞여 있다 (2026-11-06)
}


def site_of(sender):
    return next((d for d in SITES if d in sender), None)


def _clip_invoice(page, png_path):
    """광고가 많은 화면은 계산서 표만 잘라 저장 — 「합계」가 든 가장 작은 표, 없으면 전체 화면"""
    best = page.evaluate("""() => {
        const ts=[...document.querySelectorAll('table')].filter(t=>/합\\s*계/.test(t.innerText)&&/공\\s*급/.test(t.innerText));
        if(!ts.length) return null;
        ts.sort((a,b)=>a.innerText.length-b.innerText.length);
        let t=ts[ts.length>1?ts.length-1:0];  // 공급자·합계를 다 품은 바깥 표
        for(const x of ts){ if(/등록\\s*번호/.test(x.innerText)&&/합\\s*계/.test(x.innerText)){t=x;break;} }
        const r=t.getBoundingClientRect(); return {x:r.x+scrollX-10,y:r.y+scrollY-10,width:r.width+20,height:r.height+20};
    }""")
    if best and best["width"] > 300 and best["height"] > 200:
        page.screenshot(path=str(png_path), full_page=True, clip=best)
        return
    # 계산서가 iframe 안에 있는 사이트(로지스빌) — 그 iframe 만 캡처
    for sel in ("iframe[id*=inqTaxView]", "iframe[id*=Tax]"):
        el = page.query_selector(sel)
        if el:
            el.screenshot(path=str(png_path))
            return
    page.screenshot(path=str(png_path), full_page=True)


def open_agency(sender, html, account, png_path):
    """→ 화면 글자. 지원 안 하는 대행사·링크 없음·안 열림이면 예외"""
    site = site_of(sender)
    if not site:
        raise RuntimeError("자동으로 여는 방법이 아직 없는 대행사")
    link_pat, opener = SITES[site]
    m = re.search(link_pat, html)
    if not m:
        raise RuntimeError("메일 본문에서 계산서 링크를 못 찾음")
    url = m[0].replace("&amp;", "&")
    biz = _ENT[ACCOUNT_ENTITY.get(account, "블루트렌드")]["사업자번호"].replace("-", "")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page(viewport={"width": 1000, "height": 1300}, device_scale_factor=2)
            page.on("dialog", lambda d: d.dismiss())  # 「번호가 다릅니다」 같은 알림창은 닫음
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
            except Exception:
                pass  # 광고 때문에 networkidle 이 안 오는 사이트(스마트빌) — 본문만 뜨면 진행
            extra = opener(page, biz)  # 화면 글자로 안 잡히는 값(input 안의 금액 등)을 돌려주는 사이트가 있음
            page.wait_for_timeout(4000)
            text = "\n".join(f.inner_text("body") for f in page.frames) + ("\n" + extra if extra else "")
            if not re.search(r"합\s*계", text):
                raise RuntimeError("계산서 화면이 안 열림 — 사업자번호가 다르거나 화면 형식이 바뀜")
            png_path.parent.mkdir(parents=True, exist_ok=True)
            _clip_invoice(page, png_path)
        finally:
            browser.close()
    return text


def parse_agency(text):
    """작성일자(YYYYMMDD 형식도)·합계 금액"""
    t = re.sub(r"\s+", " ", text)
    date = re.search(r"작성\s*일자.*?(\d{4})[/.-]?\s*(\d{2})[/.-]?\s*(\d{2})", t)
    total = re.search(r"합\s*계\s*금?\s*액?.*?(-?\d{1,3}(?:,\d{3})+)", t)  # 반품·반환은 마이너스
    return ("-".join(date.groups()) if date else None, int(total[1].replace(",", "")) if total else None)
