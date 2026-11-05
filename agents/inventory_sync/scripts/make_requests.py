# 출고처별 주문서 파일 만들기 — 규칙 원본: shipping_request/README.md 「업체별 양식」·「기본 양식」
# 양식 있는 업체(가야김치·삼보물류·경인양행)는 지난 파일을 복사해 데이터만 교체, 그 외는 기본 양식, 천안은 카톡 텍스트
# 결과: ../output/YYMMDD/ — 원본 양식은 건드리지 않음

import datetime as dt
import glob
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import openpyxl
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

import classify

REPO = Path(__file__).resolve().parents[3]
SHIP = REPO / "shipping_request"
TPL = SHIP / "reference" / "templates"
OUTPUT = Path(__file__).resolve().parents[1] / "output"
SOFFICE = r"C:\Program Files\LibreOffice\program\soffice.exe"
BASIC_HEAD = ["배송요청일", "주문번호", "수령처", "수령인", "전화", "주소", "상품명", "규격", "수량", "요청사항", "운송장 번호"]
BASIC_WIDTH = [11, 20, 22, 10, 14, 48, 34, 14, 7, 24, 14]


def load_stores():
    """(계정, 거래처명) → 배송지. 같은 이름이 둘이면 거래상태 y 우선"""
    out = {}
    for f in glob.glob(str(SHIP / "reference" / "(마켓봄)거래처_일괄수정_엑셀양식_*.xlsx")):
        account = re.search(r"양식_(\d+)_", f)[1]
        rows = list(openpyxl.load_workbook(f, read_only=True, data_only=True).active.iter_rows(values_only=True))
        i = next(i for i, r in enumerate(rows) if r and sum(1 for c in r if c) > 8)
        head = [str(c or "").replace("*", "").strip() for c in rows[i]]
        key = next(h for h in head if h.startswith("거래처명"))
        state = next((h for h in head if h.startswith("거래상태")), None)
        for r in rows[i + 1:]:
            d = dict(zip(head, r))
            name = str(d.get(key) or "").strip()
            if name and ((account, name) not in out or str(d.get(state, "")).lower() == "y"):
                out[(account, name)] = d
    return out


def pick(d, *keys):
    for w in keys:
        for k in d:
            if w in k and d[k] not in (None, ""):
                return str(d[k]).strip()
    return ""


def addr(s):
    """→ (우편번호, 주소+상세, 수령인, 휴대폰 숫자만)"""
    road = " ".join(x for x in (pick(s, "배송지 주소", "배송지주소", "주소"), pick(s, "상세주소", "상세")) if x)
    return pick(s, "우편번호"), road, pick(s, "담당자명", "담당자"), re.sub(r"\D", "", pick(s, "휴대폰"))


def dash(tel):
    return f"{tel[:3]}-{tel[3:-4]}-{tel[-4:]}" if len(tel) >= 10 else tel


def _fill_template(template, path, make_row, stores, rows):
    shutil.copy(template, path)
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    ws.delete_rows(2, ws.max_row)
    for r in rows:
        ws.append(make_row(r, addr(stores[(r["계정"], r["거래처"])])))
    wb.save(path)


def gaya(rows, stores, path):
    _fill_template(TPL / "1019_가야김치_A-type(일반)_.xlsx", path, lambda r, a: [
        r["주문번호"], r["거래처"], a[3], a[3], a[0], a[1], r["상품명"], r["판매규격"],
        classify.ship_qty(r, "가야김치"), r["요청사항"] or None], stores, rows)


def kyungin(rows, stores, path):
    _fill_template(TPL / "경인양행_옥된장20261016.xlsx", path, lambda r, a: [
        None, str(r["주문일시"])[:10], r["거래처"], dash(a[3]), a[1], r["상품명"],
        classify.ship_qty(r, "경인양행"), r["판매규격"], r["요청사항"] or None], stores, rows)


def sambo(rows, stores, path):
    """.xls는 openpyxl로 못 씀 → 양식을 xlsx로 변환해 채운 뒤 다시 .xls로"""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = tmp / "tpl.xls"
        shutil.copy(TPL / "삼보_261016_택배리스트.xls", src)
        subprocess.run([SOFFICE, "--headless", "--convert-to", "xlsx", "--outdir", str(tmp), str(src)], check=True, timeout=120)
        wb = openpyxl.load_workbook(tmp / "tpl.xlsx")
        ws = wb.active
        ws.delete_rows(2, ws.max_row)
        ws.cell(1, 12, "주문번호")
        for i, r in enumerate(rows, 2):
            z, a, _, t = addr(stores[(r["계정"], r["거래처"])])
            day = dt.datetime.strptime(str(r["주문일시"])[:10], "%Y-%m-%d")
            for col, v in ((1, day), (2, r["거래처"]), (3, dash(t)), (4, z), (5, a), (6, r["요청사항"] or None),
                           (8, r["상품명"]), (9, r["판매규격"]), (10, classify.ship_qty(r, "삼보물류")), (12, r["주문번호"])):
                ws.cell(i, col, v)
            ws.cell(i, 1).number_format = 'mm"월" dd"일"'
        wb.save(tmp / "filled.xlsx")
        subprocess.run([SOFFICE, "--headless", "--convert-to", "xls:MS Excel 97", "--outdir", str(tmp / "x"),
                        str(tmp / "filled.xlsx")], check=True, timeout=120)
        shutil.copy(tmp / "x" / "filled.xls", path)


def basic(rows, stores, path, vendor):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "출고요청"
    ws.append(BASIC_HEAD)
    for r in rows:
        z, a, name, t = addr(stores[(r["계정"], r["거래처"])])
        ws.append([r["배송요청일"], r["주문번호"], r["거래처"], name, dash(t), f"({z}) {a}" if z else a, r["상품명"],
                   f"{r['판매규격']} / {r['단위']}", classify.ship_qty(r, vendor), r["요청사항"] or None])
    for row in ws.iter_rows():
        for c in row:
            c.font = Font(name="맑은 고딕", size=12 if c.row == 1 else 9, bold=c.row == 1)
    for i, w in enumerate(BASIC_WIDTH, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    wb.save(path)


def cheonan(rows, stores, path):
    """파일 없이 카톡으로 보내는 업체 — 복사용 텍스트"""
    days = "월화수목금토일"
    lines = ["안녕하세요, 철산장 주문 전달드립니다.", ""]
    groups = defaultdict(list)
    for r in rows:
        groups[r["거래처"]].append(r)
    for shop, items in groups.items():
        d = dt.date.fromisoformat(str(items[0]["주문일시"])[:10])
        _, a, name, t = addr(stores[(items[0]["계정"], shop)])
        lines += [f"■ 주문일: {d:%m/%d}({days[d.weekday()]})", f"■ 배송지: {shop}", f"  {a}", f"  {name} {dash(t)}", ""]
        lines += [f"- {re.sub(r'/리드타임:.*', '', str(x['상품명']))} / {x['판매규격']} / {x['수량']:g}{x['단위']}" for x in items]
        lines.append("")
    path.write_text("\n".join(lines + ["확인 부탁드립니다."]), encoding="utf-8")


def build(by_vendor, day):
    """{출고처: [주문 행]} → ({출고처: 파일}, 배송지 못 찾은 행). 배송지 없는 행은 빈칸으로 보내지 않고 돌려줌"""
    stores = load_stores()
    folder = OUTPUT / f"{day:%y%m%d}"
    folder.mkdir(parents=True, exist_ok=True)
    made, missing = {}, []
    ymd = f"{day:%y%m%d}"
    for vendor, rows in by_vendor.items():
        ok = []
        for r in rows:
            (ok if (r["계정"], r["거래처"]) in stores else missing).append(r)
        if not ok:
            continue
        if vendor == "가야김치":
            p = folder / f"{ymd}_가야김치_A-type(일반).xlsx"
            gaya(ok, stores, p)
        elif vendor == "삼보물류":
            p = folder / f"{ymd}_삼보물류_식기류 및 부자재.xls"
            sambo(ok, stores, p)
        elif vendor == "경인양행":
            p = folder / f"경인양행_{day:%Y%m%d}.xlsx"
            kyungin(ok, stores, p)
        elif vendor == "천안축산물유통센터":
            p = folder / f"{ymd}_천안축산물유통센터_주문문구.txt"
            cheonan(ok, stores, p)
        else:
            p = folder / f"{ymd}_{vendor}_출고요청.xlsx"
            basic(ok, stores, p, vendor)
        made[vendor] = p
    return made, missing
