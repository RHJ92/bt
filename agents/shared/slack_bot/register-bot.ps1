# 슬랙 #지시 봇을 PC 로그온 때 자동 시작하도록 작업 스케줄러에 등록한다.
#
# 실행: powershell -ExecutionPolicy Bypass -File register-bot.ps1
# 해제: powershell -ExecutionPolicy Bypass -File register-bot.ps1 -Unregister
#
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다 (Windows PowerShell 5.1 한글 인식).

param([switch]$Unregister)

$ErrorActionPreference = 'Stop'

$taskName = '슬랙 지시 봇 (로그온 시 시작)'
$runner   = Join-Path $PSScriptRoot 'run-bot.ps1'

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "기존 작업 제거: $taskName"
}
if ($Unregister) { Write-Host '해제 완료.'; exit 0 }

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $runner)

$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"

# 봇은 계속 떠 있어야 하므로 실행 시간 제한 없음, 이미 떠 있으면 새로 안 띄움
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description '슬랙 #지시 채널 글 → 회사 PC Claude Code 헤드리스 실행 → 스레드 답장. 설계: agents/shared/slack_bot/' | Out-Null

Start-ScheduledTask -TaskName $taskName
Write-Host "등록·시작 완료: $taskName"
