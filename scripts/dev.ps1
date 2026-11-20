# Start API (port 8000, localhost only) and web app (port 3000) in two windows.
#   powershell -File scripts\dev.ps1          # this computer only
#   powershell -File scripts\dev.ps1 -Phone   # also reachable from phones on the same Wi-Fi
param([switch]$Phone)

$root = Split-Path -Parent $PSScriptRoot
$web = if ($Phone) { 'npm run dev:lan' } else { 'npm run dev' }

Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root\backend'; uv run python -m uvicorn app.main:app --port 8000"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root\frontend'; $web"

Write-Host 'App  -> http://localhost:3000'
if ($Phone) {
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.InterfaceAlias -match 'Wi-Fi|Wireless|Ethernet' -and $_.IPAddress -notmatch '^(127|169\.254|172\.(1[6-9]|2\d|3[01]))\.' } |
        Select-Object -ExpandProperty IPAddress
    foreach ($ip in $ips) { Write-Host "Phone -> http://${ip}:3000  (same Wi-Fi; allow Node.js in the Windows firewall prompt)" -ForegroundColor Green }
}
