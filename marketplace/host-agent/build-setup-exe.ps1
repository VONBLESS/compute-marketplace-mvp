$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  python -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller

& ".venv\Scripts\pyinstaller.exe" `
  --noconsole `
  --onefile `
  --name marketplace-host-agent-setup `
  agent\windows_app.py

Write-Host "Build complete: $PSScriptRoot\dist\marketplace-host-agent-setup.exe"
