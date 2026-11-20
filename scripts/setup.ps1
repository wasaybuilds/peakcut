# One-time setup for clip-kr on Windows.  Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Test-Cmd($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Update-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'Machine')
}

Write-Host '==> Checking tools' -ForegroundColor Cyan
if (-not (Test-Cmd ffmpeg)) { winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements --silent }
if (-not (Test-Cmd uv))     { winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements --silent }
if (-not (Test-Cmd node))   { winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements --silent }
Update-Path

# Smart App Control blocks the unsigned python.exe that uv-managed Pythons use,
# so the venv must be built on a signed python.org interpreter.
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py -or $py -like '*WindowsApps*') {
    Write-Host '==> Installing Python 3.13 from python.org (signed)' -ForegroundColor Cyan
    winget install --id Python.Python.3.13 -e --accept-source-agreements --accept-package-agreements --silent
    Update-Path
    $py = (Get-Command python).Source
}

Write-Host '==> Backend (uv)' -ForegroundColor Cyan
Push-Location "$root\backend"
$env:UV_PYTHON_DOWNLOADS = 'never'
if (-not (Test-Path .venv)) { uv venv --python $py }
uv sync
uv run python -c "import pydantic_core, jiter, fastapi, faster_whisper; print('backend imports OK')"
Pop-Location

Write-Host '==> Frontend (npm)' -ForegroundColor Cyan
Push-Location "$root\frontend"
npm install
Pop-Location

if (-not (Test-Path "$root\.env")) {
    Copy-Item "$root\.env.example" "$root\.env"
    Write-Host '==> Created .env - add your free API keys to it.' -ForegroundColor Yellow
}

Write-Host "`nDone. Start everything with:  powershell -File scripts\dev.ps1" -ForegroundColor Green
