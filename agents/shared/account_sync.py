# 계정보관/계정목록.xlsx → 자동화가 쓰는 곳(자격 증명 관리자·환경변수·shared/config)에 반영
# 실행: 계정보관/계정반영.bat 더블클릭, 또는 python -X utf8 account_sync.py
# 새 PC에서는 폴더 복사 후 이것만 실행하면 복구된다 (계정보관/gdrive-mcp 가 있으면 구글 인증도)
# 비밀번호는 화면·로그에 찍지 않는다. 계정보관/ 은 깃 제외(.gitignore)

import json
import os
import shutil
import winreg
from pathlib import Path

import keyring
import openpyxl

REPO = Path(__file__).resolve().parents[2]
BOOK = REPO / "계정보관" / "계정목록.xlsx"
CFG = Path(__file__).resolve().parent / "config"
GDRIVE_HOME = Path.home() / ".gdrive-mcp"
GDRIVE_SAVED = REPO / "계정보관" / "gdrive-mcp"


def save_id(file, key, user):
    p = CFG / file
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if d.get(key) != user:
        d[key] = user
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def set_env(name, value):
    """사용자 환경변수 — 레지스트리에 직접 (값이 명령줄에 안 남게)"""
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)


def restore_gdrive():
    """새 PC에 구글 인증이 없으면 보관본에서 복구"""
    if GDRIVE_SAVED.exists() and not (GDRIVE_HOME / "credentials.json").exists():
        shutil.copytree(GDRIVE_SAVED, GDRIVE_HOME, dirs_exist_ok=True)
        print("복구: 구글 인증(.gdrive-mcp)")


def main():
    restore_gdrive()
    ws = openpyxl.load_workbook(BOOK, data_only=True).active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    done = same = skip = 0
    for service, _name, _url, user, pw, code, *_ in [r + (None,) * 8 for r in rows]:
        if not code or not user or not pw:
            skip += 1
            continue
        kr, _, key = str(code).partition(":")
        user, pw = str(user).strip(), str(pw)
        if kr == "env":
            if os.environ.get(key) == pw:
                same += 1
            else:
                set_env(key, pw)
                done += 1
                print(f"반영: {service}")
            continue
        if keyring.get_password(kr, user) == pw:
            same += 1
        else:
            keyring.set_password(kr, user, pw)
            done += 1
            print(f"반영: {service}")
        if kr == "marketbom":
            save_id("marketbom.json", key, user)
        elif kr == "jette-ebiz":
            save_id("jette_accounts.json", key, user)
        elif kr == "amb-wms":
            (CFG / "wms_amb.json").write_text(json.dumps({"id": user}), encoding="utf-8")
        elif kr == "swc-wms":
            (CFG / "wms_swc.json").write_text(json.dumps({"id": user}), encoding="utf-8")
    print(f"완료 — 변경 {done}건, 그대로 {same}건, 건너뜀(비밀번호 칸 비었거나 자동화 미사용) {skip}건")


if __name__ == "__main__":
    main()
