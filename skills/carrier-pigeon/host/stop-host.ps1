# Stops carrier-pigeon-host and its child sessions (claude / codex app-server). Not run by Grok Bot.
$root = if ($env:CARRIER_PIGEON_HOME) { $env:CARRIER_PIGEON_HOME } else { Join-Path $HOME '.carrier-pigeon' }
$lock = Join-Path $root 'host\host.lock'
if (-not (Test-Path $lock)) { 'carrier-pigeon-host not running'; exit 0 }
$hp = [int](Get-Content $lock)
& taskkill.exe /PID $hp /T /F 2>$null | Out-Null   # /T kills the child tree too
Remove-Item $lock -ErrorAction SilentlyContinue
"stopped carrier-pigeon-host (pid $hp)"
