@echo off
chcp 65001 >nul
start "" http://127.0.0.1:8765
python -X utf8 "%~dp0app.py"
