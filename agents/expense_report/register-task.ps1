# 계산서 수집 예약 작업을 Windows 작업 스케줄러에 등록한다.
#
# 실행: powershell -ExecutionPolicy Bypass -File register-task.ps1
# 해제: powershell -ExecutionPolicy Bypass -File register-task.ps1 -Unregister
#
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다 (Windows PowerShell 5.1 한글 인식).

param([switch]$Unregister)

$ErrorActionPreference = 'Stop'

$taskName = '계산서 수집 (월-금 10시·17시)'
$runner   = Join-Path $PSScriptRoot 'run-invoice-intake.ps1'

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

$days = 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'
$trigger = @(
    (New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At '10:00'),
    (New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At '17:00')
)

# StartWhenAvailable: 정해진 시각에 PC가 꺼져 있었으면 켜고 로그인했을 때 놓친 실행을 따라잡는다.
# WakeToRun: 절전 모드면 깨워서 실행한다.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

# 로그온한 사용자 계정으로 실행 — 자격 증명 관리자(이카운트 메일 비밀번호)와 토스트 알림이 이 세션에 묶여 있다.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description '월~금 10:00·17:00 이카운트 메일 계산서 수집(국세청 보안메일 열어 PNG 저장) → 노션 첨부 대기 목록 + 슬랙. 설계: agents/expense_report/README.md §7' | Out-Null

$info = Get-ScheduledTaskInfo -TaskName $taskName
Write-Host "등록 완료: $taskName"
Write-Host ("  다음 실행: " + $info.NextRunTime)
