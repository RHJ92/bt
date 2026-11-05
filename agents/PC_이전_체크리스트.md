# 에이전트 PC 이전 체크리스트

작성 2026-11-02. 지금 PC → 다른 PC로 옮길 때 폴더 복사만으로 안 되는 것 정리.

**1. 폴더째 복사** (깃에 없으므로 git clone으로는 안 옴)
- `bt/` 전체. 특히 깃 제외분: `계정보관/`, `agents/shared/config/`, `agents/**/state/`, `agents/**/logs/`, `agents/inventory_sync/output/`
- `C:\Users\BLUETREND\.gdrive-mcp\` — 구글 인증 (시트·드라이브 전부)
- `C:\Users\BLUETREND\.claude\projects\…\memory\` — 작업 메모. 폴더 이름이 저장소 경로에서 만들어지므로 경로가 같아야 그대로 읽힘
- 바탕화면 `지출결의 증빙 이미지\`

**2. 복사로 안 옮겨지고 새 PC에서 다시 할 것**
- 비밀번호·토큰·환경변수: `계정보관\계정반영.bat` 하나로 복구. 슬랙 토큰 2행·노션 토큰 1행은 사용자가 계정목록.xlsx에 직접 넣어 둔 경우에 복구됨. 구글 인증은 `계정보관\gdrive-mcp\`에 복사해 두면 함께 복구
- 사업자번호는 `agents/shared/entities.json` 파일이라 다시 등록할 것 없음
- 작업 스케줄러: 슬랙 지시 봇(`register-bot.ps1`), 제때 일일 조회(`jette_daily/register-task.ps1`), 축산품 주간 실측, 회의록 자동정리 등. 등록은 사용자가 직접 실행
- Python + 패키지: playwright keyring requests openpyxl xlrd pypdf pymupdf slack_bolt beautifulsoup4 lxml
- LibreOffice(`C:\Program Files\LibreOffice`), Chrome, claude CLI, PC 카카오톡

**3. 로그인 다시**
- 크롬: 노션(bt1005 계정), BT FLOW, Claude 확장 연결 → 새 브라우저 deviceId를 `shared/slack_bot/bot.py` SYSTEM에 교체
- 마켓봄·제때 ebiz는 다른 IP에서 추가 인증이 뜰 수 있음 — 등록 스크립트로 확인

**4. 경로 확인**
- 스크립트 일부에 `C:\Users\BLUETREND` 가 고정돼 있음: `jette_daily/scripts/run_daily.py`, `shared/gsheet.py`, 각 `set_*password.py`, `shared/slack_bot/claude_stop_hook.py`
- 새 PC 사용자 폴더·저장소 경로가 같으면 그대로 동작. 다르면 먼저 수정

**5. 옮긴 날 확인 순서**
1. 옛 PC의 봇·스케줄러를 먼저 끈다 — **두 PC가 동시에 돌면 발주·입고확인이 이중 입력됨**
2. 새 PC에서 `계정반영.bat` → 슬랙 토큰 → 봇 등록
3. 슬랙에서 간단한 지시 1건, 재고수불·마켓봄 로그인 1회, 시트 읽기 확인
4. 다음 날 08:10~09:00 자동 실행 결과 확인
