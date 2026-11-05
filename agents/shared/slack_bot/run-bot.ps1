# 슬랙 #지시 봇 상시 실행 (PC 로그온 때 작업 스케줄러가 호출). 창 없이 pythonw 로 띄움
# 수동 실행: powershell -ExecutionPolicy Bypass -File run-bot.ps1
# 이 파일은 UTF-8 with BOM 으로 저장해야 한다 (Windows PowerShell 5.1 한글 인식).

$py = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\pythonw.exe' }
$env:PYTHONIOENCODING = 'utf-8'
Set-Location $PSScriptRoot
Start-Process -FilePath $py -ArgumentList '-X', 'utf8', (Join-Path $PSScriptRoot 'bot.py') -WindowStyle Hidden
