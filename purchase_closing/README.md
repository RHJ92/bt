# purchase_closing — 제때 매입마감 검토

구글시트 「DAILY 업무 진행_발주,단가,코드」(ID `1x1KueQVbAyKYQJV_3pkcHZhJc5YJqjSbadiCIr3tRns`)의 발주진행현황·매입사마감을 제때 정산과 대조하고, 팀장 검토 전후로 무엇이 바뀌었는지 추적하는 거점.

**구조**
- `sheet_snapshot.py` — 시트 탭 스냅샷 저장 / 두 스냅샷 비교 / 드라이브 수정 이력 조회
- `snapshots/<YYMMDD_라벨>/` — 탭별 JSON(표시값 + 수식) + 그 시점 제때 구매정산 CSV
- `YYMMDD_*.md` — 건별 검토 기록

**스냅샷 대상 탭**: 10월_발주진행현황 / 매입사마감 / 신_품목리스트 / 신_단가변동사항 / 중간단가변경이력 / 종합현황 (월이 바뀌면 `TABS` 첫 항목 수정)

**사용법** (저장소 루트 기준, 한글 출력 깨지면 `-X utf8`)
- 저장: `python -I -X utf8 purchase_closing/sheet_snapshot.py snap 261019_팀장검토후`
- 비교: `python -I -X utf8 purchase_closing/sheet_snapshot.py diff 261016_검토전 261019_팀장검토후`
  - 결과 유형: 입력변경 / 수식변경 / 수식→값 덮어씀 / 계산결과변경
- 수정자·시각: `python -I -X utf8 purchase_closing/sheet_snapshot.py revs`
- 인증: `C:\Users\BLUETREND\.gdrive-mcp\` OAuth(읽기 전용) — 저장소 밖, 회사 PC에만 있음

**제때 정산 데이터**: ebiz.jette.co.kr → 발주관리 → 구매 정산내역 조회 → 마감월·매입사 블루트렌드 조회. 화면 그리드 `gridCS06100Top_T1._dataSource.getJsonRow(i)`로 읽음(FIX_IN_DATE·ITEMID·FIX_IN_QTY·UNIT_PRICE·SUPPLY_PRICE·VAT)

**검토 기준**
- 단가 비교 대상 = 발주진행현황 W열 jt단가(VAT 별도), X jt매입단가(공급가), Y jt부가세, Z jt매입가
- 제때는 단가 원 단위 반올림 후 × 수량, 시트는 VAT 포함가 ÷ 1.1 미반올림 → 행당 ±100원대 차이는 정상
- 같은 날 같은 코드 ±동량 = 단가 정정, 정상 단가로 −1 = 1개 차감 → 시트에 행 없음, 조정분으로 따로 집계
