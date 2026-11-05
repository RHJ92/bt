# 받은 마켓봄 주문 엑셀 읽기 — 깨진 구형 .xls라 xlrd 옵션 필수, 1행 빈 행·2행 머리글

from pathlib import Path

import xlrd


def read(path):
    s = xlrd.open_workbook(str(path), ignore_workbook_corruption=True, encoding_override="cp949").sheet_by_index(0)
    head = s.row_values(1)
    account = Path(path).name.split("_")[0]
    return [{**dict(zip(head, s.row_values(i))), "계정": account} for i in range(2, s.nrows)]
