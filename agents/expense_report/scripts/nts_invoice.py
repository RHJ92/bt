# 국세청 전자세금계산서 보안메일(NTS_eTaxInvoice.html) 열기 → PNG 캡처 + 본문 글자
# 비밀번호 = 받는 법인 사업자번호(숫자만) — agents/shared/entities.json. 다르면 자격 증명 관리자 "nts-invoice"에 덮어쓰기(set_nts_password.py)
# 브라우저는 PC에 설치된 크롬(Playwright channel="chrome", 창 안 띄움)

import json
import re
import tempfile
from pathlib import Path

import keyring
from playwright.sync_api import sync_playwright

KEYRING_SERVICE = "nts-invoice"
_ENT = {k: v for k, v in json.loads((Path(__file__).resolve().parents[2] / "shared" / "entities.json")
                                    .read_text(encoding="utf-8")).items() if not k.startswith("_")}
ENTITIES = tuple(_ENT)  # 받는 법인 키 (블루트렌드·블루푸드랩·옥된장·철산장·석문어·정백선)


def password_of(entity):
    return keyring.get_password(KEYRING_SERVICE, entity) or _ENT[entity]["사업자번호"].replace("-", "")


def _split(subject):
    """제목 '받는법인 (공급자->받는법인)' → (공급자, 받는법인). 이름 안의 (주) 괄호 때문에 '->' 기준으로 자름"""
    if "->" not in subject:
        return subject, ""
    left, right = subject.rsplit("->", 1)
    recipient = right.strip().removesuffix(")").strip()
    prefix = recipient + " ("
    supplier = left[len(prefix):] if left.startswith(prefix) else left.split(" (", 1)[-1]
    return supplier.strip(), recipient


def entity_of(subject):
    """받는 법인 → '블루트렌드' / '블루푸드랩' / None. 블루트랜드 오기 포함"""
    recipient = _split(subject)[1].replace(" ", "")
    return next((e for e, v in _ENT.items() if any(a in recipient for a in v["별칭"])), None)


def supplier_of(subject):
    return _split(subject)[0]


def open_invoice(html_bytes, entity, png_path):
    """보안메일을 풀어 png_path 로 캡처하고 화면 글자를 돌려줌. 비밀번호 없거나 실패하면 예외"""
    pw = password_of(entity)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "NTS_eTaxInvoice.html"
        src.write_bytes(html_bytes)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            try:
                page = browser.new_page(viewport={"width": 900, "height": 1200}, device_scale_factor=2)
                page.goto(src.as_uri(), wait_until="networkidle", timeout=60000)
                page.fill("#idPcPwd", pw)
                page.evaluate("InputPwd()")
                page.wait_for_timeout(2500)
                if page.locator("#idPcPwd").is_visible():
                    raise RuntimeError("보안메일이 안 열림 — 사업자번호가 틀렸거나 화면 형식이 바뀜")
                # 계산서 본문은 안쪽 프레임(CriMsgPosition)에 그려짐 → 글자는 전 프레임, 캡처는 그 프레임만
                text = "\n".join(f.inner_text("body") for f in page.frames)
                png_path.parent.mkdir(parents=True, exist_ok=True)
                frame = page.frame("CriMsgPosition")
                if frame:
                    frame.frame_element().screenshot(path=str(png_path))
                else:
                    page.screenshot(path=str(png_path), full_page=True)
            finally:
                browser.close()
    return text


def parse_text(text):
    """캡처 화면 글자에서 작성일자·합계금액 (못 찾으면 None)"""
    # 표가 「제목줄 → 값줄」 순서라 제목 뒤 첫 날짜·첫 금액을 잡음 (예: 작성일자 … 2026/ 10/ 29 / 합계금액 … 1,872,000)
    t = re.sub(r"\s+", " ", text)
    date = re.search(r"작성\s*일자.*?(\d{4})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{1,2})", t)
    total = re.search(r"합계\s*금액.*?(\d{1,3}(?:,\d{3})+|\d{4,})", t)
    return ("-".join(f"{int(x):02d}" if i else x for i, x in enumerate(date.groups())) if date else None,
            int(total[1].replace(",", "")) if total else None)
