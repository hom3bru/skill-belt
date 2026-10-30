# Starts carrier-pigeon-host. Default: foreground (Ctrl+C stops). -Background: hidden window. Not run by Grok Bot.
param([switch]$Background)
$ErrorActionPreference = 'Stop'
$root = if ($env:CARRIER_PIGEON_HOME) { $env:CARRIER_PIGEON_HOME } else { Join-Path $HOME '.carrier-pigeon' }
$hostJs = Join-Path $root 'host\carrier-pigeon-host.mjs'
New-Item -ItemType Directory -Force (Join-Path $root 'host\logs') | Out-Null
if ($Background) {
  $p = Start-Process node -ArgumentList "`"$hostJs`" start" -WindowStyle Hidden -PassThru `
       -RedirectStandardOutput (Join-Path $root 'host\logs\stdout.log') -RedirectStandardError (Join-Path $root 'host\logs\stderr.log')
  "carrier-pigeon-host started in background (pid $($p.Id))"
} else { node $hostJs start }
