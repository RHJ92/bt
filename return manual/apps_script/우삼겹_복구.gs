/**
 * 우삼겹슬라이스 탭 복구 — 아롱사태 탭(우삼겹과 서식 동일)을 복제해 재생성 후
 * 사용자 최종본 내용으로 채웁니다. (팀장 원본 대신 최신 내용)
 *
 * 실행: 함수 '우삼겹_복구' 선택 → 실행. 완료 후 목차 다음(2번째) 위치로 이동합니다.
 * ※ 6열(A~F) 구조 기준. 아롱사태 탭이 있어야 동작합니다(서식 원본으로 사용).
 */

var FORMAT_SRC = '아롱사태';
var COLS = 6;

var WOO = {
 "sheet": "우삼겹슬라이스",
 "title": "우삼겹슬라이스",
 "storage": "냉동 (-18℃ 이하)",
 "unit": "BOX (10kg/BOX)",
 "suppliers": [
  "신우미트(선우프레시) — CC311143 우삼겹슬라이스S",
  "신우미트(캐틀팜/케이팩토리) — CC310895 우삼겹슬라이스C",
  "신우미트(미트이노베이션) — CC311145 우삼겹슬라이스M"
 ],
 "reasons": [
  "① 해동 흔적: 배송 중 온도 관리 실패로 고기가 녹아 핏물이 흘러나왔거나, 다시 얼면서 박스 안에 얼음덩어리가 크게 뭉쳐 있는 경우",
  "② 속포장 훼손: 고기를 감싼 속비닐이 찢어져 고기가 공기에 노출되어 색이 변하거나 마른 경우 (겉박스만 눌리거나 찢어진 것은 유의사항 참조)",
  "③ 썰기 불량·부스러기 과다: 썰린 두께가 고르지 않아 심하게 부서지거나, 조리에 쓸 수 없는 자투리·부스러기가 지나치게 많이 섞인 경우",
  "④ 이물 발견: 제조 과정에서 비위생적인 이물이 들어간 경우",
  "⑤ 비계 뭉치 혼입: 특정 팩에 비계가 상당한 비중으로 들어 있어 정상적인 조리·판매가 어려운 경우 (지방 비율의 차이 자체는 부위 특성 — 유의사항 참조)",
  "⑥ 변색·냄새 (수령 당일 확인분): 수령 당일 넓은 범위의 검은 변색이나 이상한 냄새가 확인된 경우 — 해당 중량만큼 반품 (표면 지방의 옅은 갈변은 가공 특성상 정상 — 유의사항 참조)",
  "⑦ 다른 상품 입고: 주문한 상품·규격과 다른 제품이 입고된 경우"
 ],
 "steps": [
  [
   "STEP 1",
   "수령 즉시 확인",
   "• 아래 '3. 수령 검수 체크리스트'를 순서대로 확인합니다.\n• 이 품목은 특히 변색·냄새를 수령 당일 반드시 확인해 주세요 (당일 이후에는 반품이 어렵습니다).",
   "가맹점"
  ],
  [
   "STEP 2",
   "사진 촬영",
   "• 박스 라벨(상품명·제조일)이 보이는 전체 사진 + 문제 부위 근접 사진을 확보합니다.\n• 변색·냄새 반품은 박스 라벨, 포장 상태, 문제 부위, 해당 부위 무게 사진 4종이 필요합니다.",
   "가맹점"
  ],
  [
   "STEP 3",
   "구매팀 보고",
   "• 사진과 반품 사유를 수령 당일 구매팀 카카오톡으로 보고합니다.",
   "가맹점→구매팀"
  ],
  [
   "STEP 4",
   "반품 등록",
   "• 구매팀이 내용 확인 후 제때 시스템에 반품 등록합니다.",
   "구매팀"
  ],
  [
   "STEP 5",
   "반품 반출",
   "• 회수 전까지 반품 상품을 사용하지 말고 냉동(-18℃ 이하) 상태로 따로 보관합니다.\n• 회수 일정에 방문한 배송 기사에게 전달합니다.",
   "가맹점+제때기사"
  ],
  [
   "STEP 6",
   "정산 처리",
   "• 물류센터 검수 후 정상품 교환 배송 또는 당월 청구 대금에서 차감 처리됩니다.",
   "구매팀"
  ]
 ],
 "checklist": [
  [
   "1",
   "주문 일치",
   "발주 코드·규격과 실물 라벨 대조",
   "주문한 상품과 정확히 일치",
   "즉시 보고 후 반품"
  ],
  [
   "2",
   "무게",
   "박스 표기(10kg) 대비 실제 무게 확인",
   "허용 오차 이내",
   "저울 사진 보고 후 차액 정산 또는 반품"
  ],
  [
   "3",
   "냉동 상태",
   "핏물 흘러나옴·박스 안 얼음뭉침 확인",
   "완전히 얼어 있고 핏물·얼음뭉침 없음",
   "당일 사진 보고 후 반품"
  ],
  [
   "4",
   "속포장 상태",
   "속비닐 찢김으로 고기가 공기에 노출·마름 확인",
   "속비닐 온전",
   "속비닐 훼손+품질 저하 시 당일 보고 후 반품"
  ],
  [
   "5",
   "색·냄새 (당일 필수)",
   "포장 투명면으로 색 확인, 개봉 팩 냄새 확인",
   "선홍빛 유지, 이상한 냄새 없음",
   "당일 사진 4종 보고 후 해당 중량 반품"
  ],
  [
   "6",
   "썰기 상태",
   "부서짐·자투리 비율 확인",
   "고른 두께, 소량 부스러기 정상 범위",
   "사진 보고 후 반품 협의"
  ]
 ],
 "notes": [
  "⚠ 표면 지방의 옅은 갈변은 대부분 변질이 아닙니다: 우삼겹은 냉동 원육을 해동해 기계로 썬 뒤 다시 냉동하는 2차 가공 제품이라, 이 과정에서 지방이 공기(산소)와 닿아 옅게 갈변할 수 있습니다. 또 고기가 겹쳐 눌린 부분이 어둡게 보이는 것도 산소가 닿지 않아 생기는 일시적 현상으로, 펼쳐서 잠시 두면 선홍색으로 돌아옵니다. 반면 넓은 범위의 검은 변색에 냄새가 함께 나면 다른 문제이므로 수령 당일 바로 보고해 주세요 — 해당 중량만큼 반품됩니다.",
  "⚠ 변색·냄새는 수령 당일 보고분만 반품 가능합니다: 이 부위는 보관 온도에 따라 갈변이 쉽게 생겨, 다음날부터는 배송 문제인지 보관 문제인지 구분할 수 없기 때문입니다.",
  "⚠ 지방 비율은 박스마다 다를 수 있습니다: 소는 개체마다 살코기·지방 분포가 달라, 같은 상품도 박스에 따라 지방이 많거나 적을 수 있습니다. 이는 부위 특성으로 반품 대상이 아니며, 살코기가 많은 부위와 섞어 제공하시는 것이 요령입니다. 다만 비계 덩어리 비중이 커서 조리가 불가능한 수준이면 사진과 함께 보고해 주세요.",
  "⚠ 겉박스 눌림·찢김만으로는 반품 대상이 아닙니다: 배송 과정에서 겉박스에 생기는 손상은 일정 부분 감수가 필요하며, 속비닐이 온전해 내용물 품질에 이상이 없으면 정상 사용해 주세요. 속비닐까지 훼손되어 고기가 마르거나 변색된 경우가 반품 대상입니다.",
  "⚠ 조금이라도 해동되었다면 다시 얼리지 마세요: 얇게 썬 고기는 재냉동하면 서로 엉겨 붙어 다시 해동할 때 심하게 부서집니다. 당일 사용분만 냉장고에서 해동하고, 보관 중 속비닐이 뜯긴 팩은 색이 변하기 전에 가장 먼저 사용해 주세요."
 ]
};

function 우삼겹_복구() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  var names = ss.getSheets().map(function (s) { return s.getName(); });
  Logger.log('현재 탭: ' + names.join(' | '));

  var src = ss.getSheetByName(FORMAT_SRC);
  if (!src) throw new Error('서식 원본 탭(' + FORMAT_SRC + ')을 찾을 수 없습니다.');

  var L = analyzeTemplate(src);
  Logger.log('구조: ' + JSON.stringify(L));

  var old = ss.getSheetByName('우삼겹슬라이스');
  if (old) ss.deleteSheet(old);

  var sh = src.copyTo(ss);
  sh.setName('우삼겹슬라이스');
  fillFast(sh, WOO, L);

  // 목차 다음(2번째)으로 이동. 목차 없으면 맨 앞(1번째).
  var pos = ss.getSheetByName('목차') ? 2 : 1;
  ss.setActiveSheet(sh);
  ss.moveActiveSheet(pos);

  SpreadsheetApp.flush();
  Logger.log('완료: 우삼겹슬라이스 재생성 (위치 ' + pos + ')');
}

// ---------- 구조 분석 ----------
function analyzeTemplate(tpl) {
  var last = tpl.getLastRow();
  var vals = tpl.getRange(1, 1, last, COLS).getValues();
  function A(r) { return String(vals[r - 1][0] || '').trim(); }
  function findRow(pred) { for (var r = 1; r <= last; r++) if (pred(A(r))) return r; return -1; }

  var infoRow = findRow(function (a) { return a === '보관조건'; });

  function single(marker) {
    var h = findRow(function (a) { return a.indexOf(marker) === 0; });
    var start = h + 1;
    var vc = 1;
    for (var c = 0; c < COLS; c++) { if (String(vals[start - 1][c] || '').trim() !== '') { vc = c + 1; break; } }
    var cnt = 0;
    while (start - 1 + cnt < last && String(vals[start - 1 + cnt][vc - 1] || '').trim() !== '') cnt++;
    var mr = tpl.getRange(start, 1, 1, COLS).getMergedRanges();
    var span = mr.length ? [mr[0].getColumn(), mr[0].getLastColumn()] : [1, COLS];
    return { start: start, count: cnt, valueCol: vc, span: span };
  }

  var h2 = findRow(function (a) { return a.indexOf('■ 2') === 0; });
  var stepStart = h2 + 2;
  var stepCnt = 0;
  while (stepStart - 1 + stepCnt < last && A(stepStart + stepCnt).indexOf('STEP') === 0) stepCnt++;

  var h3 = findRow(function (a) { return a.indexOf('■ 3') === 0; });
  var chkStart = h3 + 2;
  var chkCnt = 0;
  while (chkStart - 1 + chkCnt < last && /^\d+$/.test(A(chkStart + chkCnt))) chkCnt++;

  return {
    titleRow: infoRow - 1, infoRow: infoRow,
    sup: single('■ 공급처'), reasons: single('■ 1'),
    steps: { start: stepStart, count: stepCnt },
    check: { start: chkStart, count: chkCnt },
    notes: single('■ 4')
  };
}

// ---------- 채우기 ----------
function fillFast(sh, item, L) {
  sh.getRange(L.titleRow, 1).setValue(item.title);
  sh.getRange(L.infoRow, 3).setValue(item.storage);
  sh.getRange(L.infoRow, 6).setValue(item.unit);
  writeSingle(sh, L.notes, item.notes);
  writeGrid(sh, L.check, item.checklist.map(function (r) { return [r[0], r[1], r[2], r[3], '', r[4]]; }), [[4, 5]]);
  writeGrid(sh, L.steps, item.steps.map(function (s) { return [s[0], s[1], s[2], '', s[3], '']; }), [[3, 4], [5, 6]]);
  writeSingle(sh, L.reasons, item.reasons);
  writeSingle(sh, L.sup, item.suppliers);
}

function newRow() { var a = []; for (var c = 0; c < COLS; c++) a.push(''); return a; }

function writeSingle(sh, S, values) {
  adjustRows(sh, S.start, S.count, values.length, [S.span]);
  if (!values.length) return;
  var grid = values.map(function (v) { var row = newRow(); row[S.valueCol - 1] = v; return row; });
  sh.getRange(S.start, 1, values.length, COLS).setValues(grid);
}

function writeGrid(sh, S, rows, mergeSpans) {
  adjustRows(sh, S.start, S.count, rows.length, mergeSpans);
  if (!rows.length) return;
  var grid = rows.map(function (r) {
    var row = newRow();
    for (var c = 0; c < COLS && c < r.length; c++) row[c] = r[c] == null ? '' : r[c];
    return row;
  });
  sh.getRange(S.start, 1, rows.length, COLS).setValues(grid);
}

function adjustRows(sh, start, cur, need, mergeSpans) {
  if (need > cur) {
    var add = need - cur;
    sh.insertRowsAfter(start + cur - 1, add);
    sh.getRange(start, 1, 1, COLS).copyTo(sh.getRange(start + cur, 1, add, COLS), { formatOnly: true });
    for (var k = 0; k < add; k++) {
      var r = start + cur + k;
      sh.getRange(r, 1, 1, COLS).breakApart();
      for (var m = 0; m < mergeSpans.length; m++) {
        var s = mergeSpans[m];
        sh.getRange(r, s[0], 1, s[1] - s[0] + 1).merge();
      }
    }
  } else if (need < cur) {
    sh.deleteRows(start + need, cur - need);
  }
}
