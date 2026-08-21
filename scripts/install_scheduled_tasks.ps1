param(
    [string]$PythonPath = "C:\Users\2024980\AppData\Local\Python\bin\python.exe",
    [string]$ProjectDirectory = (Split-Path -Parent $PSScriptRoot),
    [string]$DailyTaskName = "Redmine 24시간 알림 자동화",
    [string]$WeeklyTaskName = "레드마인 오픈 이슈 알림",
    [string]$DailyTime = "10:00",
    [string]$WeeklyTime = "13:30"
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $ProjectDirectory "redmine_notifier.py"
if (-not (Test-Path -LiteralPath $PythonPath)) { throw "Python not found: $PythonPath" }
if (-not (Test-Path -LiteralPath $scriptPath)) { throw "Notifier not found: $scriptPath" }

$backupDirectory = Join-Path $ProjectDirectory "scheduler-backup"
New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
foreach ($taskName in @($DailyTaskName, $WeeklyTaskName)) {
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Export-ScheduledTask -TaskName $taskName | Set-Content -LiteralPath (Join-Path $backupDirectory "$taskName-$timestamp.xml") -Encoding UTF8
    }
}

$dailyAction = New-ScheduledTaskAction -Execute $PythonPath -Argument ('"{0}" daily' -f $scriptPath) -WorkingDirectory $ProjectDirectory
$weeklyAction = New-ScheduledTaskAction -Execute $PythonPath -Argument ('"{0}" weekly' -f $scriptPath) -WorkingDirectory $ProjectDirectory
$dailyTrigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $DailyTime
$weeklyTrigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Monday -At $WeeklyTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 15) -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $DailyTaskName -Action $dailyAction -Trigger $dailyTrigger -Settings $settings -Principal $principal -Description "평일 Redmine 변경 이슈를 Teams로 요약 전송" -Force | Out-Null
Register-ScheduledTask -TaskName $WeeklyTaskName -Action $weeklyAction -Trigger $weeklyTrigger -Settings $settings -Principal $principal -Description "월요일 Handler별 Open/장기 미처리 이슈를 Teams로 리마인드" -Force | Out-Null

Write-Output "Scheduled tasks updated. Backups: $backupDirectory"
