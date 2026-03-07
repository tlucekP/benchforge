# Load environment variables from .env file into the current PowerShell session.
# Usage: . .\load_env.ps1

$envFile = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path $envFile)) {
    Write-Warning ".env file not found at $envFile"
    return
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]+)=(.+)$") {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        Write-Host "Loaded: $key" -ForegroundColor Green
    }
}
