[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ConfigPath = "",
    [ValidateRange(1, 1000)]
    [int]$Count = 10
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$config = if ($ConfigPath) {
    (Resolve-Path -LiteralPath $ConfigPath).Path
} else {
    (Resolve-Path -LiteralPath (Join-Path $root "config.toml")).Path
}
$executable = Join-Path $root ".venv\Scripts\x2telegram.exe"
$logDirectory = Join-Path $root "var\logs"
$logPath = Join-Path $logDirectory ("scheduler-{0}.jsonl" -f (Get-Date -Format "yyyyMMdd"))

if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "x2telegram executable is missing from the project virtual environment."
}
if (-not (Test-Path -LiteralPath $logDirectory)) {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
}

$exitCode = 70
$status = "launcher_failure"
$summary = ""

try {
    $output = @(& $executable run --config $config --count $Count --quiet 2>&1)
    $exitCode = $LASTEXITCODE
    $text = $output -join "`n"
    if ($exitCode -eq 0) {
        $status = "success"
        $match = [regex]::Match(
            $text,
            "(?im)^Fetched:\s*\d+;\s*matched:\s*\d+;\s*new:\s*\d+;\s*sent chunks:\s*\d+\s*$"
        )
        $summary = if ($match.Success) { $match.Value.Trim() } else { "completed" }
    }
    elseif ($text -match "(?i)another x2telegram run is already active") {
        $status = "already_running"
        $exitCode = 75
    }
    elseif ($text -match "(?i)(X credentials are not ready|bird.+(?:failed|not ready)|session cookies)") {
        $status = "x_auth_or_source_failure"
    }
    elseif ($text -match "(?i)(coding agent|Codex CLI|summarizer|ignore-user-config)") {
        $status = "coding_agent_failure"
    }
    elseif ($text -match "(?i)(TELEGRAM_(?:BOT_TOKEN|CHAT_ID)|Telegram API|Telegram credentials)") {
        $status = "telegram_failure"
    }
    elseif ($text -match "(?i)(state|seen-tweets)") {
        $status = "state_failure"
    }
    else {
        $status = "application_failure"
    }
}
catch {
    $exitCode = 70
    $status = "launcher_failure"
}

$record = [ordered]@{
    timestamp = (Get-Date).ToString("o")
    status = $status
    exitCode = $exitCode
    count = $Count
    summary = $summary
}
$json = $record | ConvertTo-Json -Compress
Add-Content -LiteralPath $logPath -Value $json -Encoding utf8
Write-Output $json
exit $exitCode
