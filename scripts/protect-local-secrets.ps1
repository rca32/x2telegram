[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
$administratorsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
$protected = New-Object System.Collections.Generic.List[string]

foreach ($name in @(".env", "x-oauth.env")) {
    $path = Join-Path $root $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        continue
    }

    $file = [System.IO.FileInfo]::new($path)
    $acl = [System.IO.FileSystemAclExtensions]::GetAccessControl(
        $file,
        [System.Security.AccessControl.AccessControlSections]::Access
    )
    $acl.SetAccessRuleProtection($true, $false)
    $existingRules = $acl.GetAccessRules(
        $true,
        $true,
        [System.Security.Principal.SecurityIdentifier]
    )
    foreach ($existingRule in $existingRules) {
        [void]$acl.RemoveAccessRuleSpecific($existingRule)
    }
    foreach ($sid in @($currentSid, $systemSid, $administratorsSid)) {
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid,
            [System.Security.AccessControl.FileSystemRights]::FullControl,
            [System.Security.AccessControl.InheritanceFlags]::None,
            [System.Security.AccessControl.PropagationFlags]::None,
            [System.Security.AccessControl.AccessControlType]::Allow
        )
        [void]$acl.AddAccessRule($rule)
    }
    [System.IO.FileSystemAclExtensions]::SetAccessControl($file, $acl)
    $protected.Add($name)
}

[pscustomobject]@{
    ProjectRoot = $root
    ProtectedFiles = @($protected)
} | ConvertTo-Json -Compress
