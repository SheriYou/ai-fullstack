# 注册 Windows 计划任务：每天 03:00 清理过期测试产出物
# 用法（管理员 PowerShell）:
#   .\scripts\schedule_daily_cleanup.ps1
#   .\scripts\schedule_daily_cleanup.ps1 -RetentionDays 14 -Hour 2
param(
    [int]$RetentionDays = 7,
    [int]$Hour = 3,
    [int]$Minute = 0
)

$ErrorActionPreference = "Stop"
$FrameworkRoot = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) {
    Write-Error "python not found in PATH"
}

$TaskName = "AgentHumanTest-DailyCleanup"
$Script = Join-Path $FrameworkRoot "scripts\daily_cleanup.py"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`" --retention-days $RetentionDays" -WorkingDirectory $FrameworkRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At ([DateTime]::Today.AddHours($Hour).AddMinutes($Minute))
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Write-Host "  Daily at $($Hour.ToString('00')):$($Minute.ToString('00'))"
Write-Host "  Retention: $RetentionDays days"
Write-Host "  Command: python `"$Script`" --retention-days $RetentionDays"
Write-Host ""
Write-Host "Manual run: python `"$Script`" --dry-run"
Write-Host "Force run:  python `"$Script`" --force"
