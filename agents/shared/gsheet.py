# 구글시트 읽기·쓰기 공용 함수 — 업무 폴더가 가져다 쓴다
# 인증: C:\Users\BLUETREND\.gdrive-mcp\ (저장소 밖) — credentials.json 읽기 전용 / credentials_rw.json 쓰기

import json
import urllib.parse
from pathlib import Path

import requests

CRED_DIR = Path(r"C:\Users\BLUETREND\.gdrive-mcp")
DAILY_SHEET = "1x1KueQVbAyKYQJV_3pkcHZhJc5YJqjSbadiCIr3tRns"  # DAILY 업무 진행_발주,단가,코드


def token(rw=False):
    keys = json.loads((CRED_DIR / "gcp-oauth.keys.json").read_text(encoding="utf-8"))["installed"]
    cred = json.loads((CRED_DIR / ("credentials_rw.json" if rw else "credentials.json")).read_text(encoding="utf-8"))
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": keys["client_id"], "client_secret": keys["client_secret"],
        "refresh_token": cred["refresh_token"], "grant_type": "refresh_token"})
    r.raise_for_status()
    return r.json()["access_token"]


def get_values(tok, rng, render="FORMATTED_VALUE", sheet=DAILY_SHEET):
    r = requests.get(f"https://sheets.googleapis.com/v4/spreadsheets/{sheet}/values/{urllib.parse.quote(rng)}"
                     f"?valueRenderOption={render}", headers={"Authorization": "Bearer " + tok})
    r.raise_for_status()
    return r.json().get("values", [])


def tab_titles(tok, sheet=DAILY_SHEET):
    r = requests.get(f"https://sheets.googleapis.com/v4/spreadsheets/{sheet}?fields=sheets.properties.title",
                     headers={"Authorization": "Bearer " + tok})
    r.raise_for_status()
    return [s["properties"]["title"] for s in r.json()["sheets"]]
