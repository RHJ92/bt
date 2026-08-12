# 클로바노트 내보내기 감시 -> 회의록 자동 정리 (매시 정각, Windows 작업 스케줄러가 호출)
#
# 하는 일: 다운로드 폴더에서 클로바노트 파일 감지 -> 텍스트 추출 -> claude 헤드리스로 노션 페이지 생성
#          -> 성공 시 원본을 드라이브 '노션 업로드 완료' 폴더에 업로드 -> 처리 이력 기록 -> 토스트 알림
#
# 수동 실행: powershell -ExecutionPolicy Bypass -File run-clovanote-watch.ps1
#   -DryRun   감지까지만 하고 claude 실행/업로드/기록은 하지 않는다
#
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다 (Windows PowerShell 5.1 한글 인식).

param([switch]$DryRun)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repo    = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$logDir  = Join-Path $PSScriptRoot 'logs'
$stage   = Join-Path $PSScriptRoot 'staging'
$state   = Join-Path $PSScriptRoot 'state.json'
$pyfile  = Join-Path $PSScriptRoot 'clova_pipeline.py'
$histFile = Join-Path $repo 'meeting minutes\CLAUDE.md'

# 다운로드 폴더 (클로바노트 내보내기 저장 위치)
$downloads = Join-Path $env:USERPROFILE 'Downloads'

# 드라이브 폴더 ID — 정리 완료본을 바로 '노션 업로드 완료'에 올린다.
# 루트에 두면 다른 세션이 같은 파일을 또 정리하는 중복 사고가 난다 (2026-08-03).
$doneFolder = '1RUD0rVy5vToUPKgoW56q3qaKEnutbJDL'
$dsMeeting  = '6e1e9aa5-e125-4287-8f6a-9bb900adaa03'

foreach ($d in @($logDir, $stage)) { if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null } }

$stamp   = Get-Date -Format 'yyyyMMdd_HHmmss'
$logFile = Join-Path $logDir ("clovanote_{0}{1}.log" -f $stamp, $(if ($DryRun) { '_dryrun' } else { '' }))

function Write-Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

function Show-Toast([string]$title, [string]$body) {
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null
        $esc = { param($s) $s -replace '&','&amp;' -replace '<','&lt;' -replace '>','&gt;' }
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
    } catch { Write-Log ("알림 표시 실패: " + $_.Exception.Message) }
}

# ---------------------------------------------------------------- 사전 점검
Write-Log ("실행 시작 (DryRun=" + $DryRun + ") / 감시 폴더: " + $downloads)

if (-not (Test-Path $downloads)) { Write-Log '중단: 다운로드 폴더가 없다.'; exit 1 }

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { Write-Log '중단: python 을 찾지 못했다.'; Show-Toast '회의록 자동정리 - 실패' 'python 을 찾지 못했습니다.'; exit 1 }

$claudeExe = Join-Path $env:USERPROFILE '.local\bin\claude.exe'
if (-not (Test-Path $claudeExe)) {
    $cmd = Get-Command claude -ErrorAction SilentlyContinue
    if ($cmd) { $claudeExe = $cmd.Source }
}
if (-not (Test-Path $claudeExe)) { Write-Log '중단: claude CLI 를 찾지 못했다.'; Show-Toast '회의록 자동정리 - 실패' 'claude CLI 를 찾지 못했습니다.'; exit 1 }

if (-not $env:NOTION_API_TOKEN) { $env:NOTION_API_TOKEN = [Environment]::GetEnvironmentVariable('NOTION_API_TOKEN','User') }
if (-not $env:NOTION_API_TOKEN) { Write-Log '중단: NOTION_API_TOKEN 이 없다.'; Show-Toast '회의록 자동정리 - 실패' 'NOTION_API_TOKEN 환경변수가 없습니다.'; exit 1 }

if (-not (Test-Path 'C:\Users\BLUETREND\.gdrive-mcp\credentials_rw.json')) {
    Write-Log '중단: 드라이브 쓰기 자격증명이 없다.'
    Show-Toast '회의록 자동정리 - 실패' '드라이브 쓰기 토큰(credentials_rw.json)이 없습니다.'
    exit 1
}

Set-Location $repo

# ---------------------------------------------------------------- 대상 감지
$scanJson = & $py $pyfile scan $downloads $state 2>&1 | Out-String
try { $targets = $scanJson | ConvertFrom-Json } catch { Write-Log ("중단: scan 실패 - " + $scanJson.Trim()); exit 1 }
if ($targets -eq $null) { $targets = @() }
if ($targets -isnot [array]) { $targets = @($targets) }

Write-Log ("감지된 신규 파일: " + $targets.Count + "건")
foreach ($t in $targets) { Write-Log ("  - " + $t.name) }

if ($targets.Count -eq 0) { Write-Log '처리할 파일 없음. 종료.'; exit 0 }
if ($DryRun) { Write-Log '드라이런: 여기까지.'; Show-Toast '회의록 자동정리 - 드라이런' ($targets.Count.ToString() + "건 감지 (처리 안 함)"); exit 0 }

# ---------------------------------------------------------------- 건별 처리
$okList = @(); $failList = @()

foreach ($t in $targets) {
    Write-Log ("처리 시작: " + $t.name)

    $txt = Join-Path $stage ([IO.Path]::GetFileNameWithoutExtension($t.name) + '.txt')
    $chars = & $py $pyfile extract $t.path $txt 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { Write-Log ("  추출 실패: " + $chars.Trim()); $failList += $t.name; continue }
    Write-Log ("  텍스트 추출 완료 (" + $chars.Trim() + "자)")

    $prompt = @"
회의 녹취 1건을 노션 「회의 정리」 DB에 회의록으로 정리한다. 매시 자동 실행되는 무인 작업이라 사용자에게 되물을 수 없다.

먼저 `.claude/skills/meeting-notes/SKILL.md` 를 읽고, 그 파일의 **3항(STT 교정) · 4항(페이지 속성) · 5항(본문 형식) · 7항(정리 원칙)** 을 그대로 적용한다.
그 파일을 읽지 못했으면 아무 기록도 하지 말고 즉시 실패로 끝낸다.

- 녹취 원문 파일: $txt
- 원본 파일명: $($t.name)
- 노션 data source: $dsMeeting

작업 순서:
1. 원문을 읽고 회의 성격·참석자·안건을 파악한다.
2. mcp__notion__API-post-page 로 속성만 먼저 만든다 (parent 는 {"type":"data_source_id","data_source_id":"$dsMeeting"}).
3. mcp__notion__API-update-page-markdown 의 replace_content 로 본문을 넣는다.
   한글은 유니코드 이스케이프 없이 그대로 넣는다. 이스케이프로 길게 보내면 페이로드가 잘려 실패한다.

무인 실행 규칙:
- 파일 이동·로컬 파일 작성·처리 이력 갱신은 하지 않는다. 스크립트가 처리한다.
- 참석자 속성은 `구매팀, <업체명>(외부)` 형식으로 쓴다. 개인 이름과 직함(대표·이사·차장 등)은 넣지 않는다. 내부 회의면 `대표, 구매팀, 운영팀`처럼 팀명만 쓴다.
- 회의명은 `<업체명> 통화 — <핵심 주제>` 형식. 외부 건은 업체명을 반드시 앞에 둔다.
- 확신 없는 수치·고유명사는 원문 값을 유지하고 본문 하단 「STT 확인 필요」에 남긴다.
- 적용 브랜드나 참석자 소속이 불명확하면 추정하지 말고 「STT 확인 필요」에 적는다.
- 통화 녹취는 양측 발화가 겹쳐 같은 문장이 중복 기록되므로 중복을 제거하고 정리한다.

마지막 줄에 정확히 아래 형식으로 한 줄만 출력하고 끝낸다.
RESULT: <생성한 페이지 URL> | <회의명> | <YYYY-MM-DD> | <내부미팅|외부미팅> | <관련 프로젝트>
실패했으면 RESULT: FAILED | <사유> 만 출력한다.
"@

    $claudeArgs = @(
        '-p', $prompt,
        '--mcp-config', '.mcp.json',
        '--strict-mcp-config',
        '--allowedTools', 'mcp__notion', 'Read', 'Glob', 'Grep'
    )

    Write-Log '  claude 헤드리스 실행'
    $out = & $claudeExe @claudeArgs 2>&1 | ForEach-Object {
        $line = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { $_ }
        Add-Content -Path $logFile -Value $line -Encoding utf8
        $line
    }
    $exit = $LASTEXITCODE

    $result = $null
    foreach ($line in $out) { if ($line -match '^\s*RESULT:\s*(.+)$') { $result = $Matches[1].Trim() } }

    if ($exit -ne 0 -or -not $result -or $result -like 'FAILED*') {
        Write-Log ("  실패 (exit=" + $exit + ") " + $result)
        $failList += $t.name
        continue
    }

    $parts = $result -split '\s*\|\s*'
    $url = $parts[0]; $title = $parts[1]; $date = $parts[2]; $kind = $parts[3]; $proj = $parts[4]
    Write-Log ("  노션 생성: " + $title)

    # 성공했을 때만 드라이브에 올린다 (완료 폴더로 바로 — 루트에 두면 중복 정리 위험)
    $fid = & $py $pyfile upload $t.path $doneFolder 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Write-Log ("  드라이브 업로드 실패: " + $fid.Trim() + "  -> 노션 페이지는 생성됨. 다음 실행에서 재시도하지 않도록 기록은 남긴다.")
    } else {
        Write-Log ("  드라이브 업로드 완료 (" + $fid.Trim() + ")")
    }

    # 처리 이력 (meeting minutes/CLAUDE.md 의 마커 앞에 삽입)
    try {
        $hist = Get-Content -Path $histFile -Encoding utf8
        $marker = '<!-- AUTO-LOG -->'
        $idx = ($hist | Select-String -SimpleMatch $marker | Select-Object -First 1).LineNumber
        $line = "- $date $title → 완료 ($kind, $proj) ※자동"
        if ($idx) {
            $new = @()
            $new += $hist[0..($idx-2)]
            $new += $line
            $new += $hist[($idx-1)..($hist.Count-1)]
            Set-Content -Path $histFile -Value $new -Encoding utf8
            Write-Log '  처리 이력 기록'
        } else {
            Write-Log '  처리 이력 마커를 찾지 못해 건너뜀'
        }
    } catch { Write-Log ("  처리 이력 기록 실패: " + $_.Exception.Message) }

    & $py $pyfile mark $state $t.path | Out-Null
    Remove-Item $txt -Force -ErrorAction SilentlyContinue
    $okList += $title
}

# ---------------------------------------------------------------- 결과 알림
Write-Log ("완료: 성공 " + $okList.Count + "건 / 실패 " + $failList.Count + "건")

if ($failList.Count -eq 0 -and $okList.Count -gt 0) {
    Show-Toast '회의록 자동정리 - 완료' (($okList -join ' / ') + " (" + $okList.Count + "건 노션 기록)")
} elseif ($failList.Count -gt 0) {
    Show-Toast '회의록 자동정리 - 일부 실패' ("성공 " + $okList.Count + "건 / 실패 " + $failList.Count + "건: " + ($failList -join ', ') + " · 로그: " + (Split-Path $logFile -Leaf))
}

Write-Log ("로그: " + $logFile)
if ($failList.Count -gt 0) { exit 1 } else { exit 0 }
