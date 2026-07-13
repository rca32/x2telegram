[CmdletBinding()]
param(
    [string]$TaskName = "x2telegram Timeline Digest",
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
[xml]$xml = Export-ScheduledTask -TaskName $TaskName
$namespace = [System.Xml.XmlNamespaceManager]::new($xml.NameTable)
$namespace.AddNamespace("t", "http://schemas.microsoft.com/windows/2004/02/mit/task")
$trigger = $xml.SelectSingleNode("//t:CalendarTrigger", $namespace)
$startBoundaryNode = $xml.SelectSingleNode("//t:CalendarTrigger/t:StartBoundary", $namespace)
$endBoundaryNode = $xml.SelectSingleNode("//t:CalendarTrigger/t:EndBoundary", $namespace)
$repetitionIntervalNode = $xml.SelectSingleNode("//t:CalendarTrigger/t:Repetition/t:Interval", $namespace)
$repetitionDurationNode = $xml.SelectSingleNode("//t:CalendarTrigger/t:Repetition/t:Duration", $namespace)
$latestLog = Get-ChildItem -LiteralPath (Join-Path $root "var\logs") -Filter "scheduler-*.jsonl" -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
$lastRecord = if ($latestLog) { Get-Content -LiteralPath $latestLog.FullName -Tail 1 } else { "" }
$countMatch = [regex]::Match([string]$task.Actions[0].Arguments, "(?i)-Count\s+(\d+)")

[pscustomobject]@{
    TaskName = $TaskName
    Enabled = $task.Settings.Enabled
    State = [string]$task.State
    DailyCalendarTrigger = ($null -ne $trigger)
    StartBoundary = if ($startBoundaryNode) { [string]$startBoundaryNode.InnerText } else { "" }
    EndBoundary = if ($endBoundaryNode) { [string]$endBoundaryNode.InnerText } else { "" }
    RepetitionInterval = if ($repetitionIntervalNode) { [string]$repetitionIntervalNode.InnerText } else { "" }
    RepetitionDuration = if ($repetitionDurationNode) { [string]$repetitionDurationNode.InnerText } else { "" }
    Count = if ($countMatch.Success) { [int]$countMatch.Groups[1].Value } else { $null }
    LogonType = [string]$task.Principal.LogonType
    NextRunTime = $info.NextRunTime.ToString("o")
    LastRunTime = $info.LastRunTime.ToString("o")
    LastTaskResult = $info.LastTaskResult
    StartWhenAvailable = $task.Settings.StartWhenAvailable
    RunOnlyIfNetworkAvailable = $task.Settings.RunOnlyIfNetworkAvailable
    DisallowStartIfOnBatteries = $task.Settings.DisallowStartIfOnBatteries
    StopIfGoingOnBatteries = $task.Settings.StopIfGoingOnBatteries
    WakeToRun = $task.Settings.WakeToRun
    ExecutionTimeLimit = [string]$task.Settings.ExecutionTimeLimit
    RestartCount = $task.Settings.RestartCount
    LatestSafeLogRecord = $lastRecord
} | ConvertTo-Json -Depth 4
