# 회사 PC 세팅 (BLUETREND)

## 한 번만 하는 것

1. VS Code 설치 → 확장 탭에서 Claude Code 설치
2. git-scm.com에서 Git 설치 (전부 기본값 Next) → VS Code 재시작
3. 터미널 열기: 상단 메뉴 터미널 → 새 터미널 (또는 Ctrl + ~)
4. 아래 세 줄을 한 줄씩 붙여넣고 Enter:

```
mkdir C:\Users\BLUETREND\호정\projects
cd C:\Users\BLUETREND\호정\projects
git clone https://github.com/RHJ92/personal-projects.git rhj
```

- clone 뒤의 `rhj`는 "이 이름으로 폴더 만들어 받아라"는 뜻 (저장소 이름과 달라도 됨)
- 브라우저에 GitHub 로그인 창 뜨면 RHJ92 계정 로그인 → Authorize
- clone 자체가 최초의 풀이므로 따로 풀 필요 없음

5. 파일 → 폴더 열기 → `C:\Users\BLUETREND\호정\projects\rhj` → "신뢰합니까?" 예
6. Claude 아이콘 → 집과 같은 Claude 계정으로 로그인

## 회사에서 새 세션 첫 마디

> 최신으로 받아줘. 그리고 agent_livestock_products 폴더의 CLAUDE.md를 읽고, 축산품 작업 이어서 하자.

## 알아둘 것

- 대화 기록은 PC별로 따로다. 회사의 Claude는 집에서의 대화를 모른다. 대신 CLAUDE.md(자동 로딩)와 노션(클라우드)으로 결론은 다 이어받는다. 과정·뉘앙스는 모르니, 중요한 결정은 "CLAUDE.md에 기록해줘"로 남길 것
- 노션·구글드라이브 커넥터는 Claude 계정에 붙어 있어 회사에서도 자동으로 사용 가능
- git : 인식되지 않습니다 에러 → Git 미설치. 설치 후 VS Code 완전 재시작
