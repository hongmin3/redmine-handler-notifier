param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("On", "Off", "Status")]
    [string]$State,
    [string]$ProjectDirectory = (Split-Path -Parent $PSScriptRoot)
)

$controlDirectory = Join-Path $ProjectDirectory "runtime"
$controlPath = Join-Path $controlDirectory "notification_control.json"

if ($State -eq "Status") {
    if (-not (Test-Path -LiteralPath $controlPath)) {
        Write-Output "OFF (default; control file does not exist)"
        exit 0
    }
    $current = Get-Content -LiteralPath $controlPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Output $(if ($current.enabled) { "ON" } else { "OFF" })
    exit 0
}

New-Item -ItemType Directory -Path $controlDirectory -Force | Out-Null
$enabled = $State -eq "On"
[ordered]@{
    enabled = $enabled
    changed_at = (Get-Date).ToString("o")
    changed_by = $env:USERNAME
} | ConvertTo-Json | Set-Content -LiteralPath $controlPath -Encoding UTF8

Write-Output $(if ($enabled) { "Notifications: ON" } else { "Notifications: OFF" })
