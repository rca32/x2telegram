[CmdletBinding(SupportsShouldProcess, ConfirmImpact = "High")]
param(
    [string]$TaskName = "x2telegram Timeline Digest"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    if ($PSCmdlet.ShouldProcess($TaskName, "Unregister Windows scheduled task")) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
}
