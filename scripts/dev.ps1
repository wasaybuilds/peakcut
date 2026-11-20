# Start API (port 8000) and web app (port 3000) in two windows.
$root = Split-Path -Parent $PSScriptRoot
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root\backend'; uv run python -m uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root\frontend'; npm run dev"
Write-Host 'API  -> http://localhost:8000/health'
Write-Host 'App  -> http://localhost:3000'
