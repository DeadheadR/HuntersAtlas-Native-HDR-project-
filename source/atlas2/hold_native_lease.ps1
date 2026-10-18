param([Parameter(Mandatory)][string]$WorkRoot,[Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_-]{1,80}$')][string]$Reservation)
$ErrorActionPreference='Stop'
$taskLeaseRoot=(Resolve-Path -LiteralPath $WorkRoot).Path
$taskLeasePath=Join-Path $taskLeaseRoot 'native-lease.json'
$taskReleasePath=Join-Path $taskLeaseRoot ('release-native-lease.'+$Reservation+'.request')
if(Test-Path -LiteralPath $taskReleasePath){throw 'Use a fresh release request state before taking the lease.'}
$taskLeaseMutex=[Threading.Mutex]::new($false,'Local\Piranesi.Validation.SingleWorker')
$taskLeaseOwned=$false
try {
    try {$taskLeaseOwned=$taskLeaseMutex.WaitOne(0)} catch [Threading.AbandonedMutexException] {$taskLeaseOwned=$true}
    if(!$taskLeaseOwned){throw 'The shared native lease is busy. Nothing launched.'}
    $taskConflicts=@(Get-Process -Name bb-probe,bb-play,shadps4,shadps4-qt,bloodborne,blender -ErrorAction SilentlyContinue)
    if($taskConflicts.Count){throw 'A native game or Blender process is running. Nothing launched.'}
    $taskGpu=@(& nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader)
    if($LASTEXITCODE -ne 0){throw 'Fresh GPU status unavailable. Nothing launched.'}
    $taskLeaseStarted=[DateTime]::UtcNow.ToString('o')
    $taskRecord=[ordered]@{schema=1;state='held';name='Local\Piranesi.Validation.SingleWorker';reservation=$Reservation;holder_pid=$PID;started_utc=$taskLeaseStarted;heartbeat_utc=$taskLeaseStarted;prelaunch_game_processes=0;prelaunch_blender_processes=0;release_request_path=$taskReleasePath;gpu=$taskGpu}
    while($true){
        $taskRecord.heartbeat_utc=[DateTime]::UtcNow.ToString('o')
        [IO.File]::WriteAllText($taskLeasePath+'.tmp',($taskRecord|ConvertTo-Json -Depth 5))
        Move-Item -LiteralPath ($taskLeasePath+'.tmp') -Destination $taskLeasePath -Force
        if(Test-Path -LiteralPath $taskReleasePath){
            $taskGames=@(Get-Process -Name bb-probe,bb-play,shadps4,shadps4-qt,bloodborne -ErrorAction SilentlyContinue)
            if(!$taskGames.Count){break}
        }
        Start-Sleep -Milliseconds 500
    }
} finally {
    if($taskLeaseOwned){
        $taskLeaseMutex.ReleaseMutex()
        [IO.File]::WriteAllText($taskLeasePath,([ordered]@{schema=1;state='released';name='Local\Piranesi.Validation.SingleWorker';reservation=$Reservation;holder_pid=$PID;released_utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json))
    }
    $taskLeaseMutex.Dispose()
}
