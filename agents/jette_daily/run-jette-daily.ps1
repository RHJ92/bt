# 제때 ebiz 일일 조회 → DAILY 시트 갱신 무인 실행 (월~금 08:10, Windows 작업 스케줄러가 호출)
#
# 하는 일: scripts\run_daily.py --write 실행 → 로그 저장 → 결과 토스트 알림
# 수동 실행: powershell -ExecutionPolicy Bypass -File run-jette-daily.ps1
#   -DryRun 을 붙이면 조회·비교만 하고 시트에는 쓰지 않는다.
#
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다 (Windows PowerShell 5.1 한글 인식).

param([switch]$DryRun)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

$logDir = Join-Path $PSScriptRoot 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir ("jette-daily_{0}{1}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $(if ($DryRun) { '_dryrun' } else { '' }))

function Write-Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

function Show-Toast([string]$title, [string]$body) {
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null
        $esc = { param($s) $s -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;' }
        $xml = @"
<toast duration="long">
  <visual><binding template="ToastGeneric">
    <text>$(& $esc $title)</text>
    <text>$(& $esc $body)</text>
  </binding></visual>
</toast>
"@
        $doc = New-Object Windows.Data.Xml.Dom.XmlDocument
        $doc.LoadXml($xml)
        $toast = New-Object Windows.UI.Notifications.ToastNotification $doc
        $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
    } catch {
        Write-Log ("알림 표시 실패: " + $_.Exception.Message)
    }
}

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\python.exe' }
if (-not (Test-Path $py)) {
    Write-Log '중단: python 을 찾지 못했다.'
    Show-Toast '제때 일일 조회 - 실패' 'python 을 찾지 못했습니다. 오늘은 수동으로 붙여 넣어 주세요.'
    exit 1
}

# 슬랙 업무 채널(stock)로 보냄, 확인 필요·실패는 #할일-확인필요 에도 (실패해도 무시 — 토스트가 보조)
function Send-Slack([string]$text, [string]$level) {
    try {
        $notify = Join-Path (Split-Path $PSScriptRoot -Parent) 'shared\slack_bot\notify.py'
        & $py -X utf8 $notify stock $text $level 2>&1 | Out-Null
    } catch { }
}

function Notify([string]$title, [string]$body) {
    Show-Toast $title $body
    $level = if ($title -match '실패') { 'fail' } elseif ($title -match '확인 필요|새 주 탭') { 'warn' } else { 'ok' }
    $icon = @{ fail = '❌'; warn = '⚠️'; ok = '✅' }[$level]
    Send-Slack ("$icon *$title*`n$body") $level
}

$scripts = Join-Path $PSScriptRoot 'scripts'
$pyArgs = @('-X', 'utf8', (Join-Path $scripts 'run_daily.py'))
if (-not $DryRun) { $pyArgs += '--write' }

Write-Log ("실행 시작 (DryRun=" + $DryRun + ")")
# 출근하자마자 확인하는 시트라 시작도 알림 — 누구든 슬랙에서 진행 중인지 볼 수 있게 (사용자 지시 2026-11-05)
if (-not $DryRun) {
    Send-Slack ("🔄 *제때 일일 조회 시작* ({0}) — DAILY 시트 재고·매출 갱신 중, 보통 1분 안에 끝나요. 끝나면 결과를 이어서 올려요" -f (Get-Date -Format 'MM/dd HH:mm')) 'ok'
}
Set-Location $scripts
$out = & $py @pyArgs 2>&1 | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { $_ } }
$exit = $LASTEXITCODE
$out | ForEach-Object { Add-Content -Path $logFile -Value $_ -Encoding utf8 }
Write-Log ("종료 (exit=" + $exit + ")")

$status = ($out | Where-Object { $_ -match '^STATUS:' } | Select-Object -Last 1)
$status = if ($status) { ($status -replace '^STATUS:\s*', '') } else { $null }

if ($DryRun) {
    $body = ($out | Where-Object { $_ -match '행' } | Select-Object -Last 2) -join ' / '
    Notify '제때 일일 조회 - 비교만 완료' $body
}
elseif ($exit -eq 0 -and $status) {
    # 어떤 시트·탭을 어떤 기준으로 바꿨는지 같이 (사용자 요청 2026-11-06)
    $map = @{ 'JT01036' = '매입사 블루푸드랩'; 'JT01057' = '매입사 블루트렌드' }
    $q = $out | Where-Object { $_ -match '^(재고|매출) ' } | ForEach-Object {
        $l = [string]$_; foreach ($k in $map.Keys) { $l = $l.Replace($k, $map[$k]) }; '  • ' + $l }
    $chg = $out | Where-Object { $_ -match '^\S+: 시트 \d+행 → 새 \d+행' } | ForEach-Object { '  • ' + $_ }
    $etc = $out | Where-Object { $_ -match '^(종합현황 주간 열 정렬|재고현황: 병합|\d{4}~\d{4}: 병합)' } | ForEach-Object { '  • ' + $_ }
    $body = $status + "`n*바꾼 시트:* DAILY 시트 https://docs.google.com/spreadsheets/d/1x1KueQVbAyKYQJV_3pkcHZhJc5YJqjSbadiCIr3tRns — 「재고현황」 탭 + 이번 주 매출 탭, A2:AH 값만(1행 제목·서식 유지). 종합현황은 주간 열 탭 이름 정렬 외에는 안 건드림" +
        "`n*기준:* 제때 ebiz 조회 결과로 탭 내용을 통째로 덮어씀(쓰기 전 값은 백업) — 재고 = 옥된장 본사(매입사 블루푸드랩·블루트렌드) + 철산장 전체 / 매출 = 배송일이 이번 주(월~토)인 옥된장 본사(옥된장·석문어·정백서) + 철산장" +
        "`n*조회:*`n" + ($q -join "`n") + "`n*행 수 변화:*`n" + ($chg -join "`n") + "`n*그 밖:*`n" + ($etc -join "`n")
    Notify '제때 일일 조회 - 완료' $body
}
elseif ($exit -eq 2) {
    Notify '제때 일일 조회 - 새 주 탭 필요' ($status + ' 리뉴얼하시면 다음부터 자동으로 하도록 학습합니다.')
}
else {
    $tail = if ($status) { $status } else { (($out | Select-Object -Last 2) -join ' / ') }
    if ($tail.Length -gt 200) { $tail = $tail.Substring(0, 200) + '...' }
    Notify '제때 일일 조회 - 실패 (오늘은 수동으로)' $tail
}
Write-Log ("로그: " + $logFile)
exit $exit
