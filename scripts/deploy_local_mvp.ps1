param(
    [string]$ConfigPath = "configs\bahrain-race.toml",
    [string]$PythonExe = "",
    [switch]$Open
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Resolve-Python {
    if ($PythonExe) {
        return @{ Command = $PythonExe; Prefix = @() }
    }

    $bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $bundledPython) {
        return @{ Command = $bundledPython; Prefix = @() }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @{ Command = $pyLauncher.Source; Prefix = @("-3") }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @{ Command = $python.Source; Prefix = @() }
    }

    throw "No Python runtime found. Install Python 3.11 or newer, or pass -PythonExe <path>."
}

function Invoke-ProjectPython {
    param([string[]]$Arguments)

    $runtime = Resolve-Python
    $command = $runtime.Command
    $prefix = $runtime.Prefix
    $output = & $command @prefix @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        $output | Write-Host
        exit $LASTEXITCODE
    }
    return ($output -join "`n")
}

Write-Host "Validating configuration: $ConfigPath"
$validation = Invoke-ProjectPython @("-m", "f1_telemetry_charts", "config", "validate", $ConfigPath, "--json")
$validation | Write-Host

Write-Host ""
Write-Host "Generating chart package..."
$generation = Invoke-ProjectPython @("-m", "f1_telemetry_charts", "generate", $ConfigPath, "--json")
$generation | Write-Host

$payload = $generation | ConvertFrom-Json
$outputDir = Resolve-Path $payload.output_dir
$manifestPath = Resolve-Path $payload.manifest_path

Write-Host ""
Write-Host "Local MVP deployment is ready."
Write-Host "Output directory: $outputDir"
Write-Host "Manifest: $manifestPath"
Write-Host "Charts: $(Join-Path $outputDir 'charts')"
if ($payload.observations_path) {
    Write-Host "Observations: $(Resolve-Path $payload.observations_path)"
}
if ($payload.review_path) {
    Write-Host "Review metadata: $(Resolve-Path $payload.review_path)"
}
if ($payload.markdown_path) {
    Write-Host "Markdown draft: $(Resolve-Path $payload.markdown_path)"
}

if ($Open) {
    Start-Process explorer.exe -ArgumentList $outputDir
}
