[CmdletBinding()]
param(
    [switch]$Run,
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$taskName = 'Codex Fluent Visual QA'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$entryPoint = Join-Path $root 'scripts\run_visual_qa_task.cmd'

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $taskName"
    exit 0
}

if (-not (Test-Path -LiteralPath $entryPoint -PathType Leaf)) {
    throw "Visual-QA entry point was not found: $entryPoint"
}

# InteractiveToken is deliberate: GUI automation and screen capture must run
# in the logged-in desktop session.  The task cannot run invisibly as SYSTEM,
# does not store a password, and has no elevated privileges.
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/d /c ""{0}""' -f $entryPoint) -WorkingDirectory $root
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$task = New-ScheduledTask -Action $action -Principal $principal -Settings $settings -Description 'Safe Fluent visual QA: opens only navigation pages and records local evidence. It never edits, saves, initializes, or solves a case.'

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Write-Host "Registered interactive task: $taskName"
Write-Host "Run it from Task Scheduler or: Start-ScheduledTask -TaskName '$taskName'"

if ($Run) {
    Start-ScheduledTask -TaskName $taskName
    Write-Host "Started: $taskName"
}
