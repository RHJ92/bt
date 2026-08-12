# 회의록 자동정리 (클로바노트 → 노션)

다운로드 폴더에 클로바노트 내보내기 파일이 떨어지면, **매시 정각**에 자동으로 노션 「회의 정리」 DB에 회의록을 만든다.

## 사람이 하는 일

**클로바노트에서 "텍스트 내보내기" 클릭. 끝.**

이전에는 내보내기 → 드라이브 업로드 → Claude에게 요청 3단계였다. 이제 1단계다.

> ⚠️ **자동화 켠 뒤에는 드라이브에 직접 올리지 말 것.** 스크립트가 다운로드 폴더에서 같은 파일을 또 올려 노션에 중복이 생긴다.

## 왜 클로바노트를 직접 읽지 않나

개인용 클로바노트는 **외부 연동 API를 제공하지 않는다** (네이버웍스 Business Plus 요금제만 API 지원). 브라우저 자동화로 긁는 방법은 로그인 세션·UI 변경에 계속 깨져 유지보수가 부담이라 택하지 않았다. 그래서 "내보내기 이후"를 전부 자동화하는 방식으로 만들었다.

## 흐름

```
클로바노트 내보내기 → Downloads
  ↓ (매시 정각)
1. 대상 감지        clova_pipeline.py scan   — 파일명 패턴으로 클로바노트 파일만 고름
2. 텍스트 추출      clova_pipeline.py extract — docx(python-docx) / txt(UTF-16 우선) → UTF-8
3. 노션 기록        claude 헤드리스           — SKILL.md 규칙대로 페이지 생성
4. 드라이브 보관    clova_pipeline.py upload  — '노션 업로드 완료' 폴더로 바로 업로드
5. 처리 이력        ../CLAUDE.md 의 <!-- AUTO-LOG --> 마커 앞에 한 줄 삽입
6. 상태 기록        state.json                — 재처리 방지
```

**3번이 실패하면 4~6번을 하지 않는다.** 드라이브에 올라가지도, 처리 완료로 기록되지도 않으므로 다음 시간에 자동 재시도된다.

## 구성

| 파일 | 역할 |
|---|---|
| `run-clovanote-watch.ps1` | 실행 스크립트 (스케줄러가 호출) |
| `register-task.ps1` | 작업 스케줄러 등록/해제 |
| `clova_pipeline.py` | 파일 감지·텍스트 추출·드라이브 업로드·상태 기록 |
| `logs/` | 실행별 전체 로그 (깃 미추적) |
| `staging/` | 추출한 텍스트 임시 저장. 성공하면 지운다 (깃 미추적) |
| `state.json` | 처리 완료 목록 (깃 미추적) |

등록된 작업 이름: **회의록 자동정리 (매시)**

## 잡는 파일 / 안 잡는 파일

파일명 패턴으로만 고른다. 다운로드 폴더의 다른 문서는 건드리지 않는다.

| 잡음 | 안 잡음 |
|---|---|
| `통화 녹음 *.docx` / `.txt` | `*.m4a` (오디오 원본) |
| `새로운 노트*.docx` / `.txt` | 계약서·검토의견서 등 일반 문서 |

## 설치

```powershell
powershell -ExecutionPolicy Bypass -File register-task.ps1
```

사전 조건 4가지:
1. `claude` CLI (`irm https://claude.ai/install.ps1 | iex`)
2. `NOTION_API_TOKEN` **사용자** 환경변수
3. 드라이브 쓰기 토큰 `C:\Users\BLUETREND\.gdrive-mcp\credentials_rw.json`
4. python + `python-docx`, `google-api-python-client`, `google-auth`

**최초 등록 시 기존 다운로드 파일을 자동으로 "처리 완료"로 시드한다** (오늘 0시 기준). 안 그러면 예전에 이미 정리한 회의록까지 다시 올려 노션에 중복이 생긴다.

해제:
```powershell
powershell -ExecutionPolicy Bypass -File register-task.ps1 -Unregister
```

## 손으로 돌려보기

```powershell
# 감지까지만 (처리 안 함)
powershell -ExecutionPolicy Bypass -File run-clovanote-watch.ps1 -DryRun

# 실제 실행
powershell -ExecutionPolicy Bypass -File run-clovanote-watch.ps1
```

## 무인 실행 안전장치

- **도구 최소 권한** — `--allowedTools` 에 `mcp__notion`, `Read`, `Glob`, `Grep` 만 준다. **Bash·Write·Edit 없음.** 무인 세션이 로컬 파일이나 셸을 건드릴 수 없다. 파일 조작은 전부 PowerShell/파이썬이 한다.
- **MCP 명시 지정** — `--mcp-config .mcp.json --strict-mcp-config` 로 노션 서버만 물린다.
- **완료 폴더로 직행** — 드라이브 루트를 거치지 않는다. 루트에 두면 다른 세션이 같은 파일을 또 정리하는 중복 사고가 난다 (2026-08-03 실제 발생, 페이지 4개 중복).
- **실패 시 미기록** — 노션 생성이 실패하면 상태를 남기지 않아 다음 시간에 재시도된다.
- **중복 실행 방지** — `MultipleInstances IgnoreNew`. 앞 실행이 길어져도 겹치지 않는다.
- **PC 꺼져 있던 구간 보충** — `StartWhenAvailable`. 켜지면 놓친 실행을 곧바로 한 번 돈다.

## 결과 확인

- **토스트 알림** — 성공 시 생성된 회의명, 실패 시 파일명과 로그 파일명
- **로그** — `logs/clovanote_<타임스탬프>.log` (claude 출력 전체 포함)
- **처리 이력** — `../CLAUDE.md` 처리 이력에 `※자동` 표시로 쌓임

## 한계 / 알아둘 것

- **클로바노트 STT가 끝나야** 내보낼 수 있으므로 그 클릭은 남는다. 클로바노트 앱의 통화 녹음 자동 업로드 설정을 켜두면 녹음→변환까지는 자동이 된다.
- 무인 세션은 사람에게 되물을 수 없다. 브랜드·참석자 소속이 불명확하면 추정하지 않고 본문 하단 **「STT 확인 필요」** 에 남긴다. **주기적으로 그 항목을 훑어 확정해줘야 한다.**
- 다운로드 폴더를 자주 비우면 스크립트가 보기 전에 파일이 사라질 수 있다. 정리 전에 한 번 실행하거나, 다음 정각까지 두는 편이 안전하다.
- 완전 무인(사람 손 0)으로 가려면 클로바노트를 빼고 오디오 → STT API(CLOVA Speech / Whisper) 파이프라인으로 바꿔야 한다. 그 경우에도 3~6번 뒷단은 그대로 재사용된다.
