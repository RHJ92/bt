# 축산품 주간 실측 예약 작업을 Windows 작업 스케줄러에 등록한다.
#
# 실행: powershell -ExecutionPolicy Bypass -File register-task.ps1
# 해제: powershell -ExecutionPolicy Bypass -File register-task.ps1 -Unregister
#
# PC를 옮기거나 저장소를 다시 클론했을 때 이 스크립트만 다시 돌리면 된다.
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다 (Windows PowerShell 5.1 한글 인식).

param([switch]$Unregister)

$ErrorActionPreference = 'Stop'

# 작업 이름에 콜론(:)을 쓰면 스케줄러가 거부한다 — "11:00" 대신 "11시".
$taskName = '축산품 주간 실측 (수 11시)'
$runner   = Join-Path $PSScriptRoot 'run-weekly-survey.ps1'

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "기존 작업 제거: $taskName"
}
if ($Unregister) { Write-Host '해제 완료.'; exit 0 }

if (-not (Test-Path $runner)) { throw "실행 스크립트를 찾지 못했다: $runner" }

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $runner)

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday -At '11:00'

# StartWhenAvailable: 수요일 11시에 PC가 꺼져 있었으면 다음에 켤 때 놓친 실행을 따라잡는다.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -MultipleInstances IgnoreNew

# 로그온한 사용자 계정으로 실행한다 — NOTION_API_TOKEN(사용자 환경변수)과 토스트 알림이 이 세션에 묶여 있다.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description '매주 수요일 11:00 축산품 주간 시세 실측(/weekly-survey)을 무인 실행하고 노션에 초안까지 기록한다. 결과는 Windows 알림.' | Out-Null

$t = Get-ScheduledTask -TaskName $taskName
$info = Get-ScheduledTaskInfo -TaskName $taskName
Write-Host "등록 완료: $taskName"
Write-Host ("  상태     : " + $t.State)
Write-Host ("  다음 실행: " + $info.NextRunTime)
