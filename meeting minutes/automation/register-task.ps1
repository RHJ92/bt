# 회의록 자동정리 작업 스케줄러 등록/해제
#
#   등록: powershell -ExecutionPolicy Bypass -File register-task.ps1
#   해제: powershell -ExecutionPolicy Bypass -File register-task.ps1 -Unregister
#
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다.

param([switch]$Unregister)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$taskName = '회의록 자동정리 (매시)'
$script   = Join-Path $PSScriptRoot 'run-clovanote-watch.ps1'
$state    = Join-Path $PSScriptRoot 'state.json'
$pyfile   = Join-Path $PSScriptRoot 'clova_pipeline.py'

if ($Unregister) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host ("해제 완료: " + $taskName)
    } else {
        Write-Host ("등록되어 있지 않음: " + $taskName)
    }
    return
}

if (-not (Test-Path $script)) { throw "실행 스크립트를 찾을 수 없다: $script" }

# 최초 등록 시 기존 다운로드 파일을 '처리 완료'로 시드한다.
# 안 하면 예전에 이미 정리한 회의록까지 다시 올려 노션에 중복이 생긴다.
if (-not (Test-Path $state)) {
    $downloads = Join-Path $env:USERPROFILE 'Downloads'
    $cutoff = (Get-Date).ToString('yyyy-MM-ddT00:00:00')   # 오늘 0시 이전 파일은 처리 완료로 간주
    $seed = & python $pyfile seed $downloads $state $cutoff 2>&1 | Out-String
    Write-Host ("기존 파일 시드: " + $seed.Trim())
    Write-Host "  (오늘 0시 이후 내보낸 파일은 다음 실행에서 정리됩니다)"
}

$action    = New-ScheduledTaskAction -Execute 'powershell.exe' `
                -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $script + '"')

# 매시 정각, 하루 종일 반복
$trigger   = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(([int](Get-Date).Hour) + 1) `
                -RepetitionInterval (New-TimeSpan -Hours 1)

$settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable `
                -DontStopOnIdleEnd `
                -ExecutionTimeLimit (New-TimeSpan -Minutes 50) `
                -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) `
                -LogonType Interactive -RunLevel Limited

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description '클로바노트 내보내기 파일을 감지해 노션 「회의 정리」 DB에 회의록으로 자동 기록한다. 매시 정각 실행.' | Out-Null

Write-Host ("등록 완료: " + $taskName)
Write-Host "  - 매시 정각 실행 (PC 켜져 있을 때, 놓친 실행은 켜지면 곧바로 보충)"
Write-Host "  - 로그: automation\logs\"
Write-Host "  - 해제: register-task.ps1 -Unregister"
