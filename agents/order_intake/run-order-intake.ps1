# 제때 발주 메일 → 발주진행현황 E·H·L 자동입력 무인 실행 (월~금 16:30, Windows 작업 스케줄러가 호출)
#
# 하는 일: scripts\write_orders.py --write 실행 → 로그 저장 → 결과 토스트 알림
# 수동 실행: powershell -ExecutionPolicy Bypass -File run-order-intake.ps1
#   -DryRun 을 붙이면 미리보기만 하고 시트에는 쓰지 않는다.
#
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다 (Windows PowerShell 5.1 한글 인식).

param([switch]$DryRun)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

$logDir = Join-Path $PSScriptRoot 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir ("order-intake_{0}{1}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $(if ($DryRun) { '_dryrun' } else { '' }))

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
    Show-Toast '제때 발주 자동입력 - 실패' 'python 을 찾지 못했습니다. 오늘은 수동으로 입력해 주세요.'
    exit 1
}

# 슬랙 업무 채널(order)로 보냄, 확인 필요·실패는 #할일-확인필요 에도 (실패해도 무시 — 토스트가 보조)
function Send-Slack([string]$text, [string]$level) {
    try {
        $notify = Join-Path (Split-Path $PSScriptRoot -Parent) 'shared\slack_bot\notify.py'
        & $py -X utf8 $notify order $text $level 2>&1 | Out-Null
    } catch { }
}

function Notify([string]$title, [string]$body) {
    Show-Toast $title $body
    $level = if ($title -match '실패') { 'fail' } elseif ($title -match '확인 필요|새 주 탭') { 'warn' } else { 'ok' }
    $icon = @{ fail = '❌'; warn = '⚠️'; ok = '✅' }[$level]
    Send-Slack ("$icon *$title*`n$body") $level
}

$scripts = Join-Path $PSScriptRoot 'scripts'
$pyArgs = @('-X', 'utf8', (Join-Path $scripts 'write_orders.py'))
if (-not $DryRun) { $pyArgs += '--write' }

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

if ($exit -eq 0 -and $status) {
    $title = if ($status -match '확인 필요') { '제때 발주 자동입력 - 확인 필요' } elseif ($DryRun) { '제때 발주 자동입력 - 미리보기' } else { '제때 발주 자동입력 - 완료' }
    Notify $title ($status + $note)
}
else {
    $tail = if ($status) { $status } else { (($out | Select-Object -Last 2) -join ' / ') }
    if ($tail.Length -gt 200) { $tail = $tail.Substring(0, 200) + '...' }
    Notify '제때 발주 자동입력 - 실패 (오늘은 수동으로)' $tail
}
Write-Log ("로그: " + $logFile)
exit $exit
