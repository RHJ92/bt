# 축산품 주간 실측 무인 실행 (매주 수요일 11:00, Windows 작업 스케줄러가 호출)
#
# 하는 일: 저장소 최신화 -> claude 헤드리스로 /weekly-survey 실행 -> 로그 저장 -> 결과 토스트 알림
# 수동 실행: powershell -ExecutionPolicy Bypass -File run-weekly-survey.ps1
#   -DryRun 을 붙이면 배선 점검만 하고 실제 실측/기록은 하지 않는다.
#
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다 (Windows PowerShell 5.1 한글 인식).

param([switch]$DryRun)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repo   = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$logDir = Join-Path $PSScriptRoot 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

$stamp   = Get-Date -Format 'yyyyMMdd_HHmmss'
$logFile = Join-Path $logDir ("weekly-survey_{0}{1}.log" -f $stamp, $(if ($DryRun) { '_dryrun' } else { '' }))

function Write-Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

function Show-Toast([string]$title, [string]$body) {
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null
        $esc = {
            param($s)
            $s -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;'
        }
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

# ---------------------------------------------------------------- 사전 점검
Write-Log ("실행 시작 (DryRun=" + $DryRun + ") / 저장소: " + $repo)

$claudeExe = Join-Path $env:USERPROFILE '.local\bin\claude.exe'
if (-not (Test-Path $claudeExe)) {
    $cmd = Get-Command claude -ErrorAction SilentlyContinue
    if ($cmd) { $claudeExe = $cmd.Source }
}
if (-not (Test-Path $claudeExe)) {
    Write-Log '중단: claude CLI 를 찾지 못했다.'
    Show-Toast '축산품 주간 실측 - 실패' 'claude CLI 를 찾지 못했습니다. PowerShell에서 irm https://claude.ai/install.ps1 | iex 로 재설치하세요.'
    exit 1
}
Write-Log ("claude: " + $claudeExe)

# 노션 MCP 는 이 환경변수로 인증한다. 없으면 실측해도 기록을 못 하므로 시작 전에 끊는다.
if (-not $env:NOTION_API_TOKEN) {
    $env:NOTION_API_TOKEN = [Environment]::GetEnvironmentVariable('NOTION_API_TOKEN', 'User')
}
if (-not $env:NOTION_API_TOKEN) {
    Write-Log '중단: NOTION_API_TOKEN 사용자 환경변수가 없다.'
    Show-Toast '축산품 주간 실측 - 실패' 'NOTION_API_TOKEN 환경변수가 없어 노션에 기록할 수 없습니다. 실행을 시작하지 않았습니다.'
    exit 1
}

Set-Location $repo
Write-Log '저장소 최신화 (git pull --ff-only)'
$pull = & git pull --ff-only 2>&1 | Out-String
Write-Log ("git pull: " + $pull.Trim())   # 실패해도 진행 — 로컬 기준으로 돌린다

# ---------------------------------------------------------------- 프롬프트
$statusFormat = 'STATUS: 성공|실패 · 실측 N종 · 원장 N행 · 카드 N장 · 검토요청: <한 줄>'

if ($DryRun) {
    $prompt = @"
이것은 예약 실행 배선 점검용 드라이런이다. 실제 작업은 절대 수행하지 마라.
미트박스 조회, 시세 원장 기록, 시황 카드 생성, 마스터 갱신을 모두 하지 마라.

다음 두 가지만 확인한다.
1. .claude/skills/weekly-survey/SKILL.md 를 읽어 절차가 로드되는지
2. 노션 MCP 로 품목 상태판(data source f6c565f1-f7f7-487f-99bc-f265da01b470)을 조회해 미트박스 검색어가 채워진 품목이 몇 개인지 센다

마지막 줄에 정확히 아래 형식으로 한 줄만 출력하고 끝낸다.
STATUS: 드라이런 성공|실패 · 스킬로드 O|X · 노션조회 O|X · 관측대상 N종
"@
} else {
    # 슬래시 호출(/weekly-survey)을 쓰지 않는다 — SKILL.md 에 disable-model-invocation 이 걸려 있어
    # 슬래시로는 절차가 로드되지 않는다(2026-08-06 실측 확인). 파일을 직접 읽게 한다.
    $prompt = @"
.claude/skills/weekly-survey/SKILL.md 를 먼저 읽고, 거기 적힌 0~6단계 절차를 순서대로 빠짐없이 수행하라.
배경·판단 기준은 agent_livestock_products/CLAUDE.md 를 함께 읽는다.
그 파일을 읽지 못했으면 아무 작업도 하지 말고 즉시 실패로 끝낸다.

매주 수요일 11시에 자동 실행되는 무인 예약 실행이다. 사용자에게 되물을 수 없다.

무인 실행 규칙:
- 판단이 필요하면 스킬 절차와 agent_livestock_products/CLAUDE.md 기준으로 스스로 결정하고, 확신이 없는 것은 시황 카드 시사점에 "확인 필요"로 남긴다.
- 시황 카드 검토 상태는 반드시 "초안"으로 둔다. 절대 확정하지 않는다.
- 품목 상태판의 스펙 정의·작업 MD 등 기준 문서는 수정하지 않는다 (마지막 검토일 갱신은 예외로 허용).
- 검증 게이트(전주 대비 ±10% 변동 재확인)는 생략하지 말고 그대로 수행한다.
- 노션에 접근할 수 없으면 아무것도 기록하지 말고 실패로 끝낸다.

마지막 줄에 정확히 아래 형식으로 한 줄만 출력하고 끝낸다.
$statusFormat
"@
}

# ---------------------------------------------------------------- 실행
# --mcp-config + --strict-mcp-config: 전역 승인 상태와 무관하게 .mcp.json 의 노션 서버만 물린다.
# --allowedTools: 무인 실행이므로 필요한 도구만 명시 허용 (Bash/Write/Edit 는 의도적으로 제외).
$claudeArgs = @(
    '-p', $prompt,
    '--mcp-config', '.mcp.json',
    '--strict-mcp-config',
    '--allowedTools', 'mcp__notion', 'WebFetch', 'WebSearch', 'Read', 'Glob', 'Grep', 'Skill', 'TodoWrite'
)

Write-Log 'claude 헤드리스 실행 시작'
$started = Get-Date

& $claudeExe @claudeArgs 2>&1 | ForEach-Object {
    $text = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { $_ }
    Add-Content -Path $logFile -Value $text -Encoding utf8
    Write-Host $text
}
$exit = $LASTEXITCODE

$elapsed = [int]((Get-Date) - $started).TotalMinutes
Write-Log ("claude 종료 (exit=" + $exit + ", " + $elapsed + "분 소요)")

# ---------------------------------------------------------------- 결과 검증
# 실행 세션이 마지막 STATUS 줄을 빠뜨리는 일이 잦다 (2026-08-12·08-19 실제 실행 두 번 다 누락 —
# 작업은 정상 완료했는데 알림만 "확인 필요"로 떴다). 모델의 자기보고에 기대지 말고
# 노션을 직접 조회해 오늘 기록이 실제로 남았는지 확인하고, 그 결과로 알림을 만든다.

function Get-StatusLine([string[]]$lines) {
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        if ($lines[$i] -match '^\s*STATUS:\s*(.+)$') { return $Matches[1].Trim() }
    }
    return $null
}

$logLines  = Get-Content -Path $logFile -Encoding utf8
$selfClaim = Get-StatusLine $logLines   # 실행 세션의 자기보고 (있으면 보조로 씀)
$verified  = $null

if ((-not $DryRun) -and $exit -eq 0) {
    $today = Get-Date -Format 'yyyy-MM-dd'
    $verifyPrompt = @"
무인 실행 결과 검증이다. 노션을 조회만 하고 어떤 것도 생성·수정·삭제하지 마라.

1. 시세 원장(data source b36d6ade-2001-4a80-96e2-4d4aee9f4c47)에서 「조사일」이 $today 인 행의 개수
2. 주차별 시황 카드(data source 5047f9a7-7f14-40e4-b8ac-ad3f04dba5ff)에서 「기준일」이 $today 인 카드 개수와, 그중 「검토 상태」가 초안인 개수

정확히 아래 한 줄만 출력하고 끝낸다. 설명·인사·표 금지.
STATUS: 원장 N행 · 카드 N장(초안 N)
조회에 실패했으면 대신 이 한 줄만: STATUS: 검증실패
"@
    Write-Log '노션 기록 검증 시작'
    $verifyOut = & $claudeExe -p $verifyPrompt --mcp-config '.mcp.json' --strict-mcp-config --allowedTools 'mcp__notion' 2>&1 |
        ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { $_ } }
    $verifyText = ($verifyOut -join "`n")
    Add-Content -Path $logFile -Value ("[검증] " + $verifyText) -Encoding utf8
    $verified = Get-StatusLine ($verifyText -split "`r?`n")
    Write-Log ("검증 결과: " + $(if ($verified) { $verified } else { '(STATUS 줄 없음)' }))
}

# ---------------------------------------------------------------- 결과 알림
$took = " (" + $elapsed + "분)"

if ($exit -ne 0) {
    $tail = ($logLines | Select-Object -Last 3) -join ' / '
    if ($tail.Length -gt 180) { $tail = $tail.Substring(0, 180) + '...' }
    Show-Toast '축산품 주간 실측 - 실패' ("종료코드 " + $exit + " · " + $tail)
    Write-Log '결과: 실패'
}
elseif ($DryRun) {
    if ($selfClaim) { Show-Toast '축산품 주간 실측 - 드라이런 완료' $selfClaim; Write-Log '결과: 드라이런 성공' }
    else { Show-Toast '축산품 주간 실측 - 드라이런 확인 필요' ('로그 확인: ' + (Split-Path $logFile -Leaf)); Write-Log '결과: 드라이런 STATUS 없음' }
}
elseif ($verified -and $verified -match '원장\s*(\d+)\s*행') {
    # 노션 조회로 확인된 값이 알림의 근거다.
    if ([int]$Matches[1] -gt 0) {
        Show-Toast '축산품 주간 실측 - 완료' ($verified + $took)
        Write-Log '결과: 성공 (노션 기록 확인됨)'
    } else {
        Show-Toast '축산품 주간 실측 - 확인 필요' ('정상 종료했으나 오늘 날짜로 노션에 기록된 행이 없습니다. 로그: ' + (Split-Path $logFile -Leaf))
        Write-Log '결과: 실패 의심 (오늘 기록 0행)'
    }
}
elseif ($selfClaim) {
    Show-Toast '축산품 주간 실측 - 완료(검증 미완)' ($selfClaim + $took)
    Write-Log '결과: 실행 자기보고만 있음, 노션 검증 실패'
}
else {
    Show-Toast '축산품 주간 실측 - 확인 필요' ('정상 종료했지만 결과를 확인하지 못했습니다. 로그: ' + (Split-Path $logFile -Leaf))
    Write-Log '결과: 종료코드 0이나 STATUS·검증 모두 없음'
}

Write-Log ("로그: " + $logFile)
exit $exit
