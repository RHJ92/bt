# 3개 계정 상품별주문목록 엑셀 받기 (조회 전용) → ../state/raw/{계정}_{시작}_{끝}.xls
# 실행: python -X utf8 fetch_orders.py 2026-09-01 2026-10-31

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

import marketbom

RAW = Path(__file__).resolve().parents[1] / "state" / "raw"


def fetch(sdate, edate, status=""):
    RAW.mkdir(parents=True, exist_ok=True)
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        try:
            for account in marketbom.ACCOUNTS:
                c = b.new_context()  # 계정끼리 세션이 섞이지 않게 따로
                page = c.new_page()
                page.on("dialog", lambda d: d.dismiss())
                ok, why = marketbom.saved_login(page, account)
                if not ok:
                    raise RuntimeError(f"{account} 로그인 실패 — {why}")
                path = RAW / f"{account}_{sdate}_{edate}{'_' + status if status else ''}.xls"
                path.write_bytes(marketbom.orders_excel(c, sdate, edate, status))
                out[account] = path
                c.close()
        finally:
            b.close()
    return out


if __name__ == "__main__":
    for k, v in fetch(sys.argv[1], sys.argv[2]).items():
        print(k, v.name, v.stat().st_size)
