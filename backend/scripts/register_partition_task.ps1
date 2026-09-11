$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $projectRoot 'venv\Scripts\pythonw.exe'
$script = Join-Path $PSScriptRoot 'maintain_telemetry_partitions.py'
$report = Join-Path $projectRoot 'backend\logs\partitions.json'
if (-not (Test-Path -LiteralPath $python)) { throw 'Venv pythonw.exe tidak ditemukan.' }
$arguments = '"{0}" --ensure --months 6 --report-file "{1}"' -f $script, $report
$taskName = 'FSOS-Telemetry-Partitions-Development'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    if ($existing.Actions.Execute -ne $python -or $existing.Actions.Arguments -ne $arguments) {
        throw 'Task dengan nama sama memiliki konfigurasi berbeda; tidak ditimpa.'
    }
    Write-Output 'Task sudah tersedia; konfigurasi tidak diubah.'
    exit 0
}
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $projectRoot
$triggers = @((New-ScheduledTaskTrigger -Daily -At '08:00'), (New-ScheduledTaskTrigger -AtLogOn -User $account))
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -Hidden -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Principal $principal -Settings $settings `
    -Description 'Development FSOS: siapkan enam bulan partisi telemetry UTC; tanpa penghapusan data.' | Select-Object TaskName, State
