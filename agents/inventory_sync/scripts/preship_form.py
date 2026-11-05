# 유니폼 선분출 신청 구글 폼 1회 생성 — 품목 5칸. 결과 ../state/preship_form.json
# 응답은 preship_sync.py 가 신청 시트로 옮긴다

import json
import sys
from pathlib import Path

import requests

import verify_migration as vm

STATE = Path(__file__).resolve().parents[1] / "state"
OUT = STATE / "preship_form.json"
SOURCE = "1DfGgHvHuecTGySam_TiNusUtohKFwGB4AtYG_8K_ErQ"
SLOTS = 5


def main():
    if OUT.exists():
        sys.exit("이미 있음: " + OUT.read_text(encoding="utf-8"))
    t = vm.g_token(True)
    h = {"Authorization": "Bearer " + t}
    items, head = [], False
    for r in vm.values(t, SOURCE, "MK_품목 마스터"):
        if not head:
            head = bool(r) and r[0] == "품목코드"
        elif r and any(w in str(r[0]) for w in ("유니폼", "모자")):
            items.append(str(r[0]))
    f = requests.post("https://forms.googleapis.com/v1/forms", headers=h, json={"info": {
        "title": "유니폼 선분출 신청", "documentTitle": "유니폼 선분출 신청"}}, timeout=30)
    f.raise_for_status()
    fid = f.json()["formId"]

    def q(title, question, desc=""):
        return {"title": title, "description": desc, "questionItem": {"question": question}}

    text = lambda req=True: {"required": req, "textQuestion": {"paragraph": False}}
    add = [q("신청자", text(), "이름"),
           q("브랜드", {"required": True, "choiceQuestion": {"type": "RADIO", "options": [{"value": v} for v in ("옥된장", "석문어", "정백선")]}}),
           q("매장", text()),
           q("희망 수령일", {"required": True, "dateQuestion": {"includeYear": True}}),
           q("받는 곳", text(False), "매장이 아닌 곳으로 받을 때만 입력")]
    for i in range(1, SLOTS + 1):
        req = i == 1
        add.append(q(f"품목 {i}", {"required": req, "choiceQuestion": {"type": "DROP_DOWN", "options": [{"value": v} for v in items]}}))
        add.append(q(f"수량 {i}", text(req), "숫자만"))
    add.append(q("비고", text(False)))
    reqs = [{"createItem": {"item": it, "location": {"index": i}}} for i, it in enumerate(add)]
    reqs.insert(0, {"updateFormInfo": {"info": {"description": "품목은 한 번에 5개까지 입력할 수 있습니다. 더 필요하면 한 번 더 제출해 주세요."}, "updateMask": "description"}})
    r = requests.post(f"https://forms.googleapis.com/v1/forms/{fid}:batchUpdate", headers=h, json={"requests": reqs}, timeout=60)
    r.raise_for_status()
    p = requests.post(f"https://forms.googleapis.com/v1/forms/{fid}:setPublishSettings", headers=h, timeout=30,
                      json={"publishSettings": {"publishState": {"isPublished": True, "isAcceptingResponses": True}}})
    print("게시", p.status_code)
    form = requests.get(f"https://forms.googleapis.com/v1/forms/{fid}", headers=h, timeout=30).json()
    OUT.write_text(json.dumps({"id": fid, "url": form.get("responderUri")}, ensure_ascii=False), encoding="utf-8")
    print(form.get("responderUri"))
    print(len(form.get("items", [])), "항목")


if __name__ == "__main__":
    main()
