$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$sharedPython = Join-Path $PSScriptRoot '../../work/.venv/Scripts/python.exe'
$localPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (Test-Path -LiteralPath $sharedPython) {
    $taskPython = (Resolve-Path -LiteralPath $sharedPython).Path
} elseif (Test-Path -LiteralPath $localPython) {
    $taskPython = $localPython
} else {
    $basePython = 'python'
    & $basePython -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11-3.13 is required.' }
    $taskPython = $localPython
    & $taskPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if (-not (Test-Path -LiteralPath 'data/source360.db')) {
    & $taskPython -m source360.generate --rows 100000
    if ($LASTEXITCODE -ne 0) { throw 'Data generation failed.' }
    & $taskPython -m source360.pipeline
    if ($LASTEXITCODE -ne 0) { throw 'Pipeline failed.' }
}
try {
    $ready = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2
    if ($ready.status -eq 'ok' -and $ready.synthetic) {
        Start-Process 'http://127.0.0.1:8765'
        exit
    }
} catch { }
Start-Process 'http://127.0.0.1:8765'
Write-Host 'Source360 is starting at http://127.0.0.1:8765. Keep this window open; Ctrl+C stops it.'
& $taskPython -m uvicorn source360.api:app --host 127.0.0.1 --port 8765
