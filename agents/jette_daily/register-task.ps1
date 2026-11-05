# 제때 일일 조회 예약 작업을 Windows 작업 스케줄러에 등록한다.
#
# 실행: powershell -ExecutionPolicy Bypass -File register-task.ps1
# 해제: powershell -ExecutionPolicy Bypass -File register-task.ps1 -Unregister
#
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다 (Windows PowerShell 5.1 한글 인식).

param([switch]$Unregister)

$ErrorActionPreference = 'Stop'

$taskName = '제때 일일 조회 (월-금 8시10분)'
$oldName = '제때 일일 조회 (월-토 8시10분)'  # 2026-11-05 월~금 전환 전 이름 — 남아 있으면 지움
$runner   = Join-Path $PSScriptRoot 'run-jette-daily.ps1'

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

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At '08:10'

# StartWhenAvailable: 8:10에 PC가 꺼져 있었으면 켜고 로그인했을 때 놓친 실행을 따라잡는다.
# WakeToRun: 절전 모드면 깨워서 실행한다.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

# 로그온한 사용자 계정으로 실행 — 자격 증명 관리자(ebiz 비밀번호)와 토스트 알림이 이 세션에 묶여 있다.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description '월~금 08:10 제때 ebiz 재고·매출 조회 → DAILY 시트 재고현황·주간 탭 갱신. 결과는 Windows 알림. 설계: agents/jette_daily/README.md' | Out-Null

$info = Get-ScheduledTaskInfo -TaskName $taskName
Write-Host "등록 완료: $taskName"
Write-Host ("  다음 실행: " + $info.NextRunTime)
