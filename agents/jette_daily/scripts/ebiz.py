# 제때 ebiz(ebiz.jette.co.kr) 조회 공용 함수
# 화면 그리드가 쓰는 API를 그대로 호출한다 (조회 전용 — 저장·주문 API는 쓰지 않음). 구조 조사: ../README.md §3
# 계정: ../../shared/config/jette_accounts.json 에 {"별칭": "아이디"}, 비밀번호는 Windows 자격 증명 관리자 "jette-ebiz"

import json
from pathlib import Path

import keyring
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://ebiz.jette.co.kr"
KEYRING_SERVICE = "jette-ebiz"
ACCOUNTS = Path(__file__).resolve().parents[2] / "shared" / "config" / "jette_accounts.json"

LOGIN_MSG = {
    "10": "사용자가 일치하지 않음", "15": "거래중지 ID", "20": "ID 만료", "30": "권한 없음",
    "80": "비밀번호 변경 필요", "82": "비밀번호 틀림", "85": "인증되지 않은 기기",
    "YS": "문자 인증 필요", "92": "문자 인증 만기",
}


def retrying_session():
    """연결 끊김·5xx 때 간격을 늘리며 다시 시도 (POST 포함 — 조회·전체 교체라 다시 보내도 안전)"""
    s = requests.Session()
    a = HTTPAdapter(max_retries=Retry(total=5, connect=5, read=5, backoff_factor=3, allowed_methods=None,
                                      status_forcelist=[500, 502, 503, 504], raise_on_status=False))
    s.mount("https://", a)
    return s


def load_accounts():
    return json.loads(ACCOUNTS.read_text(encoding="utf-8")) if ACCOUNTS.exists() else {}


def save_account(alias, user_id):
    acc = load_accounts()
    acc[alias] = user_id
    ACCOUNTS.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNTS.write_text(json.dumps(acc, ensure_ascii=False, indent=1), encoding="utf-8")


class Ebiz:
    def __init__(self, user_id, password=None):
        self.user_id = user_id
        self.password = password or keyring.get_password(KEYRING_SERVICE, user_id)
        if not self.password:
            raise RuntimeError(f"{user_id} 비밀번호가 저장돼 있지 않음 — set_ebiz_password.py 먼저 실행")
        self.s = retrying_session()
        self.s.headers["Content-Type"] = "application/json; charset=utf-8"
        self.s.headers["X-Requested-With"] = "XMLHttpRequest"  # 브라우저 jQuery 요청과 같게

    @classmethod
    def from_alias(cls, alias):
        acc = load_accounts()
        if alias not in acc:
            raise RuntimeError(f"계정 별칭 '{alias}' 없음 — set_ebiz_password.py 먼저 실행")
        return cls(acc[alias])

    def login(self):
        self.s.get(BASE + "/", timeout=30)
        r = self.s.post(BASE + "/api/CommonApi/Login", timeout=30, data=json.dumps({
            "userId": self.user_id, "password": self.password, "authNum": "", "rtnNum": "",
            "uniqueId": "", "remember_p_yn": "N"}))  # 웹 화면은 uniqueId = '' (앱 전용 값)
        if r.status_code == 400:
            raise RuntimeError("ebiz 로그인 요청 거절(400) — 아이디·비밀번호를 다시 확인")
        r.raise_for_status()
        code = str(r.json()[0].get("RETURN"))
        if code not in ("Y", "YY"):
            raise RuntimeError(f"ebiz 로그인 실패 [{code}] {LOGIN_MSG.get(code, '')}")
        return self

    def logout(self):
        try:
            self.s.get(BASE + "/home/logout", timeout=30)
        except requests.RequestException:
            pass

    def _grid(self, api, req):
        r = self.s.post(f"{BASE}/api/{api}", data=json.dumps(req), timeout=120)
        r.raise_for_status()
        try:
            return r.json()["_Datatable"]
        except (ValueError, KeyError):
            raise RuntimeError(f"{api} 응답이 데이터 형식이 아님 (세션 만료 또는 화면 변경)")

    def stock(self, yymmdd, owner_id, vendor_id):
        """주문대비 재고 조회 (CS06230) 상단 그리드"""
        return self._grid("CS06230/CS06230_GetDataTopGrid", {
            ":YYMMDD": yymmdd, ":OWNERID": owner_id, ":VENDORID": vendor_id, ":CENTERID": None,
            ":STOCK_TYPE": None, ":ITEM_STATUS": None, ":ITEMNAME": None})

    def sales(self, ship_from, ship_to):
        """주문내역 조회(가맹본부) (CS06050) 제품별 탭"""
        req = {k: None for k in (":ORDERDATE_FROM", ":ORDERDATE_TO", ":OWNERID", ":SHOPID", ":ITEMNAME",
                                 ":ORDER_STATE", ":ORDER_TYPE", ":CENTERID", ":ITEM_USING", ":CATEGORY1", ":CATEGORY2")}
        req[":SHIPDATE_FROM"], req[":SHIPDATE_TO"] = ship_from, ship_to
        return self._grid("CS06050/CS06050_GetGrid_TAB2", req)

    def combo(self, api, req=None):
        """화면 드롭다운 목록(고객사·매입사 등) — 철산장 계정 코드 확인용"""
        return self._grid(api, req or {})
