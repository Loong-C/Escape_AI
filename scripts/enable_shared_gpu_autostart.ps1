param([string]$TaskName = 'LinkukaiGPU')

$ErrorActionPreference = 'Stop'
$Task = Get-ScheduledTask -TaskName $TaskName
$Logon = New-ScheduledTaskTrigger -AtLogOn -User $Task.Principal.UserId
$Periodic = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 1)
# An omitted repetition duration means indefinitely. IgnoreNew prevents duplicates.
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew
Set-ScheduledTask -TaskName $TaskName -Trigger @($Logon, $Periodic) -Settings $Settings | Out-Null
Enable-ScheduledTask -TaskName $TaskName | Out-Null
Start-ScheduledTask -TaskName $TaskName
Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object LastRunTime, NextRunTime, LastTaskResult
