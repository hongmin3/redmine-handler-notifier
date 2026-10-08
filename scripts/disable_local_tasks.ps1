[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ProjectDirectory = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $ProjectDirectory).Path
$entrypoint = Join-Path $root 'redmine_notifier.py'
if (-not (Test-Path -LiteralPath $entrypoint)) { throw '대상 프로젝트의 실행 파일이 없습니다.' }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $WhatIfPreference -and -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'PC 예약 작업 중지는 관리자 권한 PowerShell에서 실행해야 합니다.'
}
$tasks = @()
foreach ($name in @('Redmine 24시간 알림 자동화', '레드마인 오픈 이슈 알림')) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $task) { continue }
    $expected = '"{0}" {1}' -f $entrypoint, $(if ($name -eq 'Redmine 24시간 알림 자동화') {'daily'} else {'weekly'})
    if (@($task.Actions).Count -ne 1 -or $task.Actions.Arguments -ne $expected -or
        (Split-Path -Leaf $task.Actions.Execute) -notin @('python.exe', 'pythonw.exe')) {
        throw "예약 작업 경로 또는 인수 불일치: $name"
    }
    $tasks += $task
}
$backup = Join-Path $root 'scheduler-backup'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
foreach ($task in $tasks) {
    if (-not $PSCmdlet.ShouldProcess($task.TaskName, 'XML 백업 후 중지·비활성화')) { continue }
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    $backupFile = Join-Path $backup ($task.TaskName + '-disabled-' + $stamp + '.xml')
    Export-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath |
        Set-Content -LiteralPath $backupFile -Encoding UTF8
    [xml]$saved = Get-Content -LiteralPath $backupFile -Raw -Encoding UTF8
    if ($saved.Task.Actions.Exec.Arguments -ne $task.Actions.Arguments) { throw '작업 백업 검증 실패' }
    Disable-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath | Out-Null
    Stop-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
    $actual = Get-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
    if ($actual.Settings.Enabled -or $actual.State -eq 'Running') { throw '작업 중지 검증 실패' }
    Write-Output ($task.TaskName + ': 비활성화 확인')
}
