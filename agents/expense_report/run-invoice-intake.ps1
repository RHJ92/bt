# 계산서 메일 수집 무인 실행 (월~금 10:00·17:00, Windows 작업 스케줄러가 호출)
#
# 하는 일: scripts\invoice_intake.py 실행 → 로그 저장. 정상 결과 슬랙은 스크립트가 직접 보냄, 실패만 여기서 알림
# 수동 실행: powershell -ExecutionPolicy Bypass -File run-invoice-intake.ps1
#   -DryRun 을 붙이면 미리보기만 하고 시트에는 쓰지 않는다.
#
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다 (Windows PowerShell 5.1 한글 인식).

param([switch]$DryRun)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

$logDir = Join-Path $PSScriptRoot 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir ("invoice-intake_{0}{1}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $(if ($DryRun) { '_dryrun' } else { '' }))

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
    Show-Toast '계산서 수집 - 실패' 'python 을 찾지 못했습니다. 오늘은 수동으로 입력해 주세요.'
    exit 1
}

# 슬랙 업무 채널(invoice)로 보냄, 확인 필요·실패는 #할일-확인필요 에도 (실패해도 무시 — 토스트가 보조)
function Send-Slack([string]$text, [string]$level) {
    try {
        $notify = Join-Path (Split-Path $PSScriptRoot -Parent) 'shared\slack_bot\notify.py'
        & $py -X utf8 $notify invoice $text $level 2>&1 | Out-Null
    } catch { }
}

function Notify([string]$title, [string]$body) {
    Show-Toast $title $body
    $level = if ($title -match '실패') { 'fail' } elseif ($title -match '확인 필요|새 주 탭') { 'warn' } else { 'ok' }
    $icon = @{ fail = '❌'; warn = '⚠️'; ok = '✅' }[$level]
    Send-Slack ("$icon *$title*`n$body") $level
}

$scripts = Join-Path $PSScriptRoot 'scripts'
$pyArgs = @('-X', 'utf8', (Join-Path $scripts 'invoice_intake.py'))


Write-Log ("실행 시작 (DryRun=" + $DryRun + ")")
Set-Location $scripts
$out = & $py @pyArgs 2>&1 | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { $_ } }
$exit = $LASTEXITCODE
$out | ForEach-Object { Add-Content -Path $logFile -Value $_ -Encoding utf8 }
Write-Log ("종료 (exit=" + $exit + ")")

$status = ($out | Where-Object { $_ -match '^STATUS:' } | Select-Object -Last 1)
$status = if ($status) { ($status -replace '^STATUS:\s*', '') } else { $null }
$result = ($out | Where-Object { $_ -match '^결과:' } | Select-Object -Last 1)
$note = if ($result) { ' · ' + (Split-Path ($result -replace '^결과:\s*', '') -Leaf) } else { '' }

if ($exit -ne 0 -or -not $status) {
    $tail = (($out | Select-Object -Last 2) -join ' / ')
    if ($tail.Length -gt 200) { $tail = $tail.Substring(0, 200) + '...' }
    Notify '계산서 수집 - 실패' $tail
}

# 이어서: 작성 대기 지결의 증빙(거래명세서) 도착 감지 — 슬랙은 스크립트가 직접 보냄, 실패만 여기서 알림
$watch = Join-Path $scripts 'evidence_watch.py'
if (Test-Path $watch) {
    Write-Log '증빙 도착 감지 시작'
    $wout = & $py -X utf8 $watch 2>&1 | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { $_ } }
    $wexit = $LASTEXITCODE
    $wout | ForEach-Object { Add-Content -Path $logFile -Value $_ -Encoding utf8 }
    $wstatus = ($wout | Where-Object { $_ -match '^STATUS:' } | Select-Object -Last 1)
    Write-Log ("증빙 감지 종료 (exit=" + $wexit + ")")
    if ($wexit -ne 0 -or -not $wstatus) {
        $wtail = (($wout | Select-Object -Last 2) -join ' / ')
        if ($wtail.Length -gt 200) { $wtail = $wtail.Substring(0, 200) + '...' }
        Notify '증빙 도착 감지 - 실패' $wtail
    }
}

Write-Log ("로그: " + $logFile)
exit $exit
