# 봇 코드를 고친 뒤 안전하게 다시 띄운다 (bot.py 의 감시 목록·주기는 시작할 때 한 번만 읽기 때문).
# 돌고 있는 담당 작업(봇의 자식 claude.exe)이 끝날 때까지 기다린 뒤 교체한다 —
# 작업 중에 그냥 죽이면 그 담당의 슬랙 답장이 안 올라간다.
#
# 실행: powershell -ExecutionPolicy Bypass -File restart-bot.ps1 [-WaitMinutes 60]
# 담당 작업(슬랙 지시) 안에서 봇 코드를 고쳤을 땐 직접 부르지 말 것 — 자기 자신이 끝나기를 기다리다 슬랙 답장이 끊긴다.
#   1회용 예약 작업으로 몇 분 뒤에 돌리고 -SelfTask '작업이름' 을 주면 끝나고 그 작업을 스스로 지운다.
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다 (Windows PowerShell 5.1 한글 인식).

param([int]$WaitMinutes = 60, [string]$SelfTask = '')

$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$log = Join-Path (Join-Path $here 'logs') 'restart.log'  # 경로를 역슬래시로 이어 쓰면 글자가 날아가 logs 안에 안 쌓임(2026-11-02 정정)

function Note($m) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Add-Content -Path $log -Value $line -Encoding utf8
}

function BotProcs {
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -like '*slack_bot*bot.py*' }
}

$ids = @((BotProcs).ProcessId)
Note ("재시작 요청 — 현재 봇 [" + ($ids -join ',') + "] / 작업 대기 최대 " + $WaitMinutes + "분")

# 1) 담당 작업이 끝날 때까지. 자식 claude.exe 가 사라진 뒤 30초 더 — 봇이 결과를 슬랙에 올릴 시간
$deadline = (Get-Date).AddMinutes($WaitMinutes)
while ((Get-Date) -lt $deadline) {
    $busy = Get-CimInstance Win32_Process -Filter "Name='claude.exe'" |
        Where-Object { $ids -contains $_.ParentProcessId }
    if (-not $busy) { Start-Sleep -Seconds 30; break }
    Start-Sleep -Seconds 15
}

# 2) 교체 — 끄고(포트 잠금 풀릴 시간을 주고) 다시 띄운다
foreach ($id in $ids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 5

$ok = $false
for ($i = 1; $i -le 3; $i++) {
    & powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $here 'run-bot.ps1')
    Start-Sleep -Seconds 20
    $new = @((BotProcs).ProcessId)
    if ($new) { Note ("재시작 완료 — 새 봇 [" + ($new -join ',') + "]"); $ok = $true; break }
    Note ("재시작 " + $i + "회차 실패 — 다시 시도")
}

if (-not $ok) {
    Note '재시작 실패 — 봇이 떠 있지 않음. run-bot.ps1 을 직접 실행할 것'
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($py) {
        & $py -X utf8 (Join-Path $here 'notify.py') todo ('🔴 슬랙 봇 재시작 실패 — 봇이 꺼져 있습니다. ' +
            'agents/shared/slack_bot/run-bot.ps1 을 직접 실행해 주세요 (기록: logs/restart.log)') fail
    }
}

# 3) 1회용 예약 작업으로 불렸으면 그 작업을 스스로 지운다
if ($SelfTask) {
    try { Unregister-ScheduledTask -TaskName $SelfTask -Confirm:$false; Note ("예약 작업 제거: " + $SelfTask) } catch { Note ("예약 작업 제거 실패: " + $_) }
}

if ($ok) { exit 0 } else { exit 1 }
