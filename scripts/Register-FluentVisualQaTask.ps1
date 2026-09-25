[CmdletBinding()]
param(
    [switch]$Run,
    [switch]$Remove,
    [switch]$CaptureCurrent,
    [switch]$ModelsTree,
    [switch]$SolutionMethods,
    [switch]$SolutionControls,
    [switch]$SolutionInitialization
)

$ErrorActionPreference = 'Stop'
$selectedModes = @($CaptureCurrent, $ModelsTree, $SolutionMethods, $SolutionControls, $SolutionInitialization) | Where-Object { $_ }
if ($selectedModes.Count -gt 1) {
    throw 'Choose only one visual-QA task mode.'
}
$taskName = if ($CaptureCurrent) { 'Codex Fluent QA Capture' } elseif ($ModelsTree) { 'Codex Fluent QA Models Tree' } elseif ($SolutionMethods) { 'Codex Fluent QA Solution Methods' } elseif ($SolutionControls) { 'Codex Fluent QA Solution Controls' } elseif ($SolutionInitialization) { 'Codex Fluent QA Solution Initialization' } else { 'Codex Fluent Visual QA' }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$entryPoint = Join-Path $root $(if ($CaptureCurrent) { 'scripts\capture_current_fluent_task.cmd' } elseif ($ModelsTree) { 'scripts\run_models_tree_visual_qa_task.cmd' } elseif ($SolutionMethods) { 'scripts\run_solution_methods_visual_qa_task.cmd' } elseif ($SolutionControls) { 'scripts\run_solution_controls_visual_qa_task.cmd' } elseif ($SolutionInitialization) { 'scripts\run_solution_initialization_visual_qa_task.cmd' } else { 'scripts\run_visual_qa_task.cmd' })

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
$description = if ($CaptureCurrent) {
    'Read-only Fluent visual-QA capture: records the current ready Fluent window without clicking or sending any command.'
} elseif ($ModelsTree) {
    'Safe Fluent visual QA: expands only the visible Models navigation-tree node and records a local frame. It never changes model settings, saves, initializes, or solves a case.'
} elseif ($SolutionMethods) {
    'Safe Fluent visual QA: opens only the Solution Methods task page and records a local frame. It never changes methods, saves, initializes, or solves a case.'
} elseif ($SolutionControls) {
    'Safe Fluent visual QA: opens only the Solution Controls task page and records a local frame. It never changes controls, saves, initializes, or solves a case.'
} elseif ($SolutionInitialization) {
    'Safe Fluent visual QA: opens only the Solution Initialization task page and records a local frame. It never initializes, saves, or solves a case.'
} else {
    'Safe Fluent visual QA: opens only navigation pages and records local evidence. It never edits, saves, initializes, or solves a case.'
}
$task = New-ScheduledTask -Action $action -Principal $principal -Settings $settings -Description $description

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Write-Host "Registered interactive task: $taskName"
Write-Host "Run it from Task Scheduler or: Start-ScheduledTask -TaskName '$taskName'"

if ($Run) {
    Start-ScheduledTask -TaskName $taskName
    Write-Host "Started: $taskName"
}
