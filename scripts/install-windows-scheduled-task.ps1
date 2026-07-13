[CmdletBinding()]
param(
    [string]$TaskName = "x2telegram Timeline Digest",
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$StartTime = "08:00",
    [string]$EndTime = "22:00",
    [ValidateRange(1, 1440)]
    [int]$IntervalMinutes = 30,
    [ValidateRange(1, 1000)]
    [int]$Count = 10,
    [switch]$AllowInitialBacklog,
    [switch]$Enable
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$config = Join-Path $root "config.toml"
$executable = Join-Path $root ".venv\Scripts\x2telegram.exe"
$runner = Join-Path $root "scripts\run-windows-scheduled-task.ps1"
$hiddenLauncher = Join-Path $root "scripts\run-windows-scheduled-task-hidden.vbs"
$protector = Join-Path $root "scripts\protect-local-secrets.ps1"
$statePath = Join-Path $root "var\seen-tweets.json"

foreach ($required in @($config, $executable, $runner, $hiddenLauncher, $protector)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required automation file is missing: $required"
    }
}
if (-not $AllowInitialBacklog -and -not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    throw "No seen-state exists. Complete one human-approved manual send first, or explicitly use -AllowInitialBacklog."
}

$culture = [System.Globalization.CultureInfo]::InvariantCulture
$start = [TimeSpan]::ParseExact($StartTime, "hh\:mm", $culture)
$end = [TimeSpan]::ParseExact($EndTime, "hh\:mm", $culture)
if ($end -le $start) {
    throw "EndTime must be later than StartTime on the same day."
}
$interval = [TimeSpan]::FromMinutes($IntervalMinutes)
$duration = ($end - $start) + $interval
$intervalXml = [System.Xml.XmlConvert]::ToString($interval)
$durationXml = [System.Xml.XmlConvert]::ToString($duration)
$startBoundary = (Get-Date).Date.Add($start).ToString("yyyy-MM-dd'T'HH:mm:ss")

& $protector -ProjectRoot $root | Out-Null
& $executable check --config $config --require-telegram
if ($LASTEXITCODE -ne 0) {
    throw "Strict x2telegram preflight failed; the scheduled task was not changed."
}
& $executable run --config $config --count $Count --dry-run --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Bounded dry-run preflight failed; the scheduled task was not changed."
}

$cscript = (Get-Command cscript.exe -ErrorAction Stop).Source
& $cscript //B //NoLogo $hiddenLauncher -ValidateOnly -Count $Count
if ($LASTEXITCODE -ne 0) {
    throw "Hidden launcher validation failed; the scheduled task was not changed."
}

$wscript = (Get-Command wscript.exe -ErrorAction Stop).Source
$arguments = '//B //NoLogo "{0}" -Count {1}' -f $hiddenLauncher, $Count
$userSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$enabledText = if ($Enable) { "true" } else { "false" }

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>x2telegram daily bounded timeline digest. Managed by the repository installer.</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <Repetition>
        <Interval>$intervalXml</Interval>
        <Duration>$durationXml</Duration>
        <StopAtDurationEnd>true</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>$startBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$userSid</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>$enabledText</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT15M</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure><Interval>PT5M</Interval><Count>2</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$([System.Security.SecurityElement]::Escape($wscript))</Command>
      <Arguments>$([System.Security.SecurityElement]::Escape($arguments))</Arguments>
      <WorkingDirectory>$([System.Security.SecurityElement]::Escape($root))</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

Register-ScheduledTask -TaskName $TaskName -Xml $xml -Force | Out-Null
& (Join-Path $root "scripts\get-windows-scheduled-task-status.ps1") -TaskName $TaskName -ProjectRoot $root
