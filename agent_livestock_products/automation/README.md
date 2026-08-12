# 주간 실측 무인 예약 실행

매주 수요일 11:00에 `/weekly-survey`(축산품 주간 시세 실측)를 사람 없이 돌려 노션에 **초안까지** 기록한다. 결과는 Windows 알림으로 뜬다.

## 왜 클라우드가 아니라 로컬인가

`/schedule`(클라우드 예약 에이전트)은 이 루틴에 못 쓴다. 노션 접근을 claude.ai OAuth 커넥터에서 **로컬 통합 토큰**(`.mcp.json` + `NOTION_API_TOKEN` 사용자 환경변수)으로 바꿨기 때문에, 클라우드 세션에는 그 토큰이 없다. 클라우드에서 돌리면 실측은 되지만 기록을 한 줄도 못 남긴다.

그래서 Windows 작업 스케줄러 + `claude` 헤드리스 실행으로 구성했다.

## 구성

| 파일 | 역할 |
|---|---|
| `run-weekly-survey.ps1` | 실제 실행 스크립트. git pull → claude 헤드리스 실행 → 로그 저장 → 토스트 알림 |
| `register-task.ps1` | 작업 스케줄러에 등록/해제 |
| `logs/` | 실행별 전체 로그 (깃 미추적) |

등록된 작업 이름: **축산품 주간 실측 (수 11시)**

## 설치 (PC를 옮겼거나 새로 클론했을 때)

```powershell
powershell -ExecutionPolicy Bypass -File register-task.ps1
```

사전 조건 3가지:
1. `claude` CLI 설치 — `irm https://claude.ai/install.ps1 | iex`
2. `NOTION_API_TOKEN` **사용자** 환경변수 등록 (없으면 스크립트가 실행 자체를 시작하지 않고 실패 알림을 띄운다)
3. 저장소 루트에 `.mcp.json` 존재

해제:
```powershell
powershell -ExecutionPolicy Bypass -File register-task.ps1 -Unregister
```

## 손으로 돌려보기

```powershell
# 배선만 점검 (실측·기록 안 함, 30초)
powershell -ExecutionPolicy Bypass -File run-weekly-survey.ps1 -DryRun

# 진짜 실행
powershell -ExecutionPolicy Bypass -File run-weekly-survey.ps1
```

## 무인 실행에 건 안전장치

- **도구 제한** — `--allowedTools` 로 노션 MCP·웹조회·읽기만 허용. Bash·Write·Edit는 뺐다. 무인 세션이 로컬 파일이나 셸을 건드릴 수 없다.
- **MCP 명시 지정** — `--mcp-config .mcp.json --strict-mcp-config`. 전역 승인 상태(`claude mcp list`의 "Pending approval")와 무관하게 노션 서버만 물린다. settings.json을 고칠 필요가 없고, 예약 작업이 자기완결적이다.
- **초안 고정** — 시황 카드는 검토 상태 "초안"으로만 만든다. 확정은 사람이 한다. (스킬 5항에 이미 박혀 있고, 프롬프트에서 한 번 더 못박는다)
- **기준 문서 불변** — 품목 상태판 스펙 정의·작업 MD는 수정 금지. 마스터의 "마지막 검토일" 갱신만 예외로 허용.
- **검증 게이트 유지** — 전주 대비 ±10% 변동 시 재확인 절차를 생략하지 않는다.
- **토큰 없으면 시작도 안 함** — 실측만 하고 기록을 못 하는 반쪽 실행을 막는다.

## 결과 확인

실행이 끝나면 토스트 알림이 뜬다.

- **완료** — `STATUS: 성공 · 실측 N종 · 원장 N행 · 카드 N장 · 검토요청: …` + 소요 시간
- **확인 필요** — 정상 종료했는데 완료 표시를 못 찾은 경우. 중간에 끊겼을 수 있으니 로그를 본다
- **실패** — 종료코드와 로그 마지막 줄

수요일 오후에 노션 「주차별 시황 카드」에서 **검토 상태 = 초안**인 카드 3장을 열어 검토·확정하면 끝난다. 특히 볼 것: ±10% 변동 품목, "스펙 매물 부재" 표시, 시사점의 "확인 필요" 항목.

## 알아둘 것

- **예약 실행은 `/weekly-survey` 슬래시 호출을 쓰지 않고 `SKILL.md`를 직접 읽게 한다.** 스킬 로드 방식(슬래시·자연어·프론트매터 설정)이 바뀌어도 예약 실행이 딸려 깨지지 않게 하려는 것.
  - 배경: 2026-08-06 대조 실험 결과, `disable-model-invocation: true`를 걸면 모델 자동 발동뿐 아니라 **슬래시 호출까지 막힌다**(슬래시도 내부적으로 Skill 도구를 거치기 때문). 무인 실행이 절차 없이 지어내는 사고로 이어질 수 있어 파일 직접 읽기로 바꿨다.
  - 그래서 프롬프트에 "SKILL.md를 읽지 못했으면 아무 작업도 하지 말고 실패로 끝내라"를 넣었다.
  - 현재 SKILL.md에 그 플래그는 **없다** — 자연어 요청("주간 실측 진행해줘")으로 부르는 게 사용자 선호. 플래그를 넣으면 자연어 호출도 함께 막히니 주의.
  - 스킬이나 프롬프트를 손댔으면 반드시 드라이런으로 "스킬로드 O"를 확인할 것.
- 작업 이름에 콜론(`:`)을 쓰면 스케줄러가 거부한다. "11:00"이 아니라 "11시"인 이유.
- 두 `.ps1`은 **UTF-8 with BOM**으로 저장해야 한다. BOM 없이 저장하면 Windows PowerShell 5.1이 ANSI로 읽어 한글이 깨진다.
- 수요일 11시에 PC가 꺼져 있었으면 다음에 켤 때 따라잡아 실행한다(`-StartWhenAvailable`). 로그온한 사용자 세션에서만 돈다 — 환경변수와 알림이 거기 묶여 있다.
- 최대 실행 시간 3시간. 넘으면 스케줄러가 끊는다.
- 집 PC에서도 쓰려면 그쪽에 `NOTION_API_TOKEN`을 등록하고 `register-task.ps1`을 한 번 돌리면 된다.
