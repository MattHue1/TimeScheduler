Set-Location $PSScriptRoot

function Test-LocalTcpPort {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutMilliseconds = 1000
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $connection.AsyncWaitHandle.WaitOne($TimeoutMilliseconds, $false)) {
            return $false
        }
        $client.EndConnect($connection)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

if (-not (Test-LocalTcpPort -HostName "127.0.0.1" -Port 8642)) {
    $hermesPath = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent\venv\Scripts\hermes.exe"
    if (-not (Test-Path -LiteralPath $hermesPath)) {
        $hermesCommand = Get-Command hermes -ErrorAction SilentlyContinue
        if ($null -eq $hermesCommand) {
            throw "Hermes is not running and hermes.exe could not be found."
        }
        $hermesPath = $hermesCommand.Source
    }

    Write-Output "Hermes is not reachable; starting the gateway."
    Start-Process -FilePath $hermesPath -ArgumentList @("gateway", "run") -WindowStyle Hidden | Out-Null

    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    do {
        Start-Sleep -Seconds 1
        $hermesReady = Test-LocalTcpPort -HostName "127.0.0.1" -Port 8642
    } while (-not $hermesReady -and [DateTime]::UtcNow -lt $deadline)

    if (-not $hermesReady) {
        throw "Hermes gateway did not become available on port 8642 within 45 seconds."
    }
}

if (-not (Test-LocalTcpPort -HostName "127.0.0.1" -Port 8081)) {
    $timeSchedulerPath = Join-Path $PSScriptRoot ".venv\Scripts\timescheduler.exe"
    if (-not (Test-Path -LiteralPath $timeSchedulerPath)) {
        throw "Time Scheduler is not running and $timeSchedulerPath could not be found."
    }

    Write-Output "Time Scheduler is not reachable; starting it."
    Start-Process `
        -FilePath $timeSchedulerPath `
        -WorkingDirectory $PSScriptRoot `
        -WindowStyle Hidden | Out-Null

    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        Start-Sleep -Seconds 1
        $timeSchedulerReady = Test-LocalTcpPort -HostName "127.0.0.1" -Port 8081
    } while (-not $timeSchedulerReady -and [DateTime]::UtcNow -lt $deadline)

    if (-not $timeSchedulerReady) {
        throw "Time Scheduler did not become available on port 8081 within 30 seconds."
    }
}

$keyLine = Get-Content ".env" |
    Where-Object { $_ -match '^TIMESCHEDULER_API_KEY=' } |
    Select-Object -First 1

$apiKey = ($keyLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
$tomorrow = (Get-Date).Date.AddDays(1).ToString("yyyy-MM-dd")

$body = @{
    request = "Return my timetable for $tomorrow only. Include all scheduled tasks and any updates, and reuse stable task IDs."
    sync_calendar = $true
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8081/api/v1/hermes/import" `
    -Headers @{ Authorization = "Bearer $apiKey" } `
    -ContentType "application/json" `
    -Body $body
