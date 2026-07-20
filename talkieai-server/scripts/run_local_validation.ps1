param(
    [string]$MainPython = "",
    [string]$OaPython = "",
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"
$serverRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repoRoot = (Resolve-Path (Join-Path $serverRoot "..")).Path
$frontendRoot = Join-Path $repoRoot "talkieai-uniapp"

if (-not $MainPython) {
    $candidate = Join-Path $serverRoot ".venv-main\Scripts\python.exe"
    if (Test-Path -LiteralPath $candidate) {
        $MainPython = $candidate
    }
}
if (-not $OaPython) {
    $candidate = Join-Path $serverRoot ".venv-oa\Scripts\python.exe"
    if (Test-Path -LiteralPath $candidate) {
        $OaPython = $candidate
    }
}

if (-not $MainPython -or -not (Test-Path -LiteralPath $MainPython)) {
    throw "Main backend Python was not found. Pass -MainPython or create talkieai-server/.venv-main."
}
if (-not $OaPython -or -not (Test-Path -LiteralPath $OaPython)) {
    throw "OA Python was not found. Pass -OaPython or install the locked environment at talkieai-server/.venv-oa."
}

$env:PYTHONUTF8 = "1"

Push-Location $serverRoot
try {
    & $MainPython -m pytest -q -p no:cacheprovider tests --ignore=tests/oa_phase1
    if ($LASTEXITCODE -ne 0) { throw "Main backend tests failed." }

    & $OaPython -m pytest -q -p no:cacheprovider tests/oa_phase1
    if ($LASTEXITCODE -ne 0) { throw "OA tests failed." }

    Push-Location (Join-Path $serverRoot "mas")
    try {
        & docker compose config --quiet
        if ($LASTEXITCODE -ne 0) { throw "Docker Compose validation failed." }
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}

Push-Location $frontendRoot
try {
    & npm.cmd run test:unit
    if ($LASTEXITCODE -ne 0) { throw "Frontend unit tests failed." }
    if (-not $SkipFrontendBuild) {
        & npm.cmd run build:h5
        if ($LASTEXITCODE -ne 0) { throw "Frontend H5 build failed." }
    }
}
finally {
    Pop-Location
}

Write-Output "LOCAL_VALIDATION=PASS"
