Set-Location "$PSScriptRoot\..\backend"
$python = Join-Path $PSScriptRoot "..\venv\Scripts\python.exe"
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
