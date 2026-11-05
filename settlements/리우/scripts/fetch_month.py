# 포장보스 월 마감 자료 자동 받기 — 브랜드별 「본부수익금 신청」·「주문 정산 내역」 엑셀 (README 월 마감 루틴 1~3단계)
# 실행: python -X utf8 fetch_month.py 2026-10            (브랜드 4개 전부 → ../statements/YYMMDD_{브랜드}_{M}월_*.xlsx)
#       python -X utf8 fetch_month.py 2026-10 석문어     (한 브랜드만)
# 로그인은 저장된 계정(pojangboss.py · 자격 증명 관리자)으로 스크립트가 직접 — 크롬 로그인 불필요. 조회·엑셀 출력만, 신청하기는 누르지 않음
# 주문 정산 내역에 주문이 없는 브랜드(육직구 등)는 「주문 0」으로 보고하고 파일을 만들지 않는다

import calendar
import datetime as dt
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

import pojangboss as pb

BRANDS = ["옥된장", "석문어", "정백선", "육직구"]
OUT = Path(__file__).resolve().parents[1] / "statements"


def switch_brand(page, name):
    if f"{name} 본부" in page.inner_text("body")[:200]:  # 이미 그 브랜드
        return
    page.goto(pb.BASE + "/", wait_until="networkidle")  # 표 안의 같은 글자(브랜드명)를 잘못 누르지 않게 대시보드에서 전환
    page.get_by_text("브랜드 변경").first.click()
    page.wait_for_timeout(1000)
    menu = page.get_by_text("선택 즉시 변경").locator("xpath=..")  # 브랜드 변경 메뉴 안에서만 찾음
    item = menu.get_by_text(name, exact=True)
    if item.count():
        item.first.click()
        for _ in range(20):  # 화면이 다시 그려질 때까지
            page.wait_for_timeout(500)
            if f"{name} 본부" in page.inner_text("body")[:200]:
                break
    else:  # 이미 현재 브랜드면 「옥된장 (현재 브랜드)」로만 보임
        page.keyboard.press("Escape")


def export(page, path):
    page.wait_for_timeout(1500)
    with page.expect_download(timeout=60000) as dl:
        page.get_by_text("엑셀 출력").first.click()
    dl.value.save_as(str(path))
    return path


def main():
    month = sys.argv[1]
    only = sys.argv[2:] or BRANDS
    y, m = map(int, month.split("-"))
    last = calendar.monthrange(y, m)[1]
    stamp = f"{dt.date.today():%y%m%d}"
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        ctx = b.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        ok, why = pb.saved_login(page)
        if not ok:
            print(f"STATUS: 실패 · 포장보스 로그인 — {why}")
            sys.exit(1)
        for name in only:
            switch_brand(page, name)
            head = page.inner_text("body")[:200]
            if f"{name} 본부" not in head:
                print(f"• {name}: 브랜드 전환 확인 안 됨 — 건너뜀")
                continue
            page.goto(f"{pb.BASE}/hq/settlement/mileage?statDateFrom={month}&statDateTo={month}", wait_until="networkidle")
            body = page.inner_text("body")
            if f"{month} " not in body and f"{month}\t" not in body and f"{month}\n" not in body:
                print(f"• {name}: 본부수익금 신청에 {month} 행 없음 (미확정 또는 주문 없음)")
                continue
            f1 = export(page, OUT / f"{stamp}_{name}_{m}월_본부수익금신청.xlsx")
            page.goto(f"{pb.BASE}/orders/sales/for-hq/boss?eventedAtFrom={month}-01&eventedAtTo={month}-{last:02d}",
                      wait_until="networkidle")
            page.get_by_text("조회", exact=True).last.click()
            page.wait_for_load_state("networkidle")
            f2 = export(page, OUT / f"{stamp}_{name}_{m}월_주문정산내역.xlsx")
            print(f"• {name}: {f1.name} · {f2.name}")
        b.close()
    print(f"STATUS: 완료 · {month} 자료 받음 → statements/")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
