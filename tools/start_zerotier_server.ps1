[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ipaddress] $Address,

    [ValidateRange(1, 65535)]
    [int] $Port = 12942,

    [ValidateNotNullOrEmpty()]
    [string] $Password,

    [string] $Admin,

    [switch] $ReuseRunningConfig,

    [switch] $AllowInbound
)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = (Resolve-Path -LiteralPath (Join-Path $project '.venv\Scripts\python.exe')).Path
$bindAddress = $Address.ToString()
$adapter = Get-NetIPAddress -AddressFamily IPv4 -IPAddress $bindAddress -ErrorAction SilentlyContinue |
    Where-Object { $_.InterfaceAlias -like 'ZeroTier*' } |
    Select-Object -First 1
if (-not $adapter) {
    throw "$bindAddress is not assigned to a local ZeroTier adapter."
}

$listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -in @($bindAddress, '0.0.0.0') })
if ($listeners.Count -gt 1) {
    throw "Multiple listeners match $bindAddress on TCP port $Port."
}
$existingArguments = $null
$gameIds = @()
if ($listeners) {
    $worker = Get-CimInstance Win32_Process -Filter "ProcessId = $($listeners[0].OwningProcess)"
    $launcher = if ($worker.ExecutablePath -eq $python) { $worker } else {
        Get-CimInstance Win32_Process -Filter "ProcessId = $($worker.ParentProcessId)"
    }
    if ($launcher.ExecutablePath -ne $python -or $worker.CommandLine -notmatch '\s-m\s+"?cold_world_game"?\s+(?:game\b|--)') {
        throw "TCP port $Port at $bindAddress is already in use by another process."
    }
    $gameIds = @(@($worker.ProcessId, $launcher.ProcessId) | Select-Object -Unique)
    $existingArguments = [regex]::Match($launcher.CommandLine, '^\s*(?:"[^"]+"|\S+)\s+(?<args>.+)$').Groups['args'].Value
}
if ($ReuseRunningConfig -and -not $existingArguments) {
    throw 'No running game was found for reusing launch options. Start it with explicit options first.'
}
if ($ReuseRunningConfig -and ($PSBoundParameters.ContainsKey('Password') -or $PSBoundParameters.ContainsKey('Admin'))) {
    throw 'Choose either existing launch options or an explicit password and administrator.'
}

$saveDirectory = "saves\zerotier-$(Get-Date -Format 'yyyyMMdd-HHmmss')-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
$savePath = Join-Path $project "$saveDirectory\world.sqlite3"
if ($ReuseRunningConfig) {
    $saveOption = [regex]::new('(?<!\S)--save-path(?:\s+|=)(?:"[^"]+"|\S+)')
    $saveArgument = '--save-path "{0}"' -f $savePath
    $launchArguments = if ($saveOption.IsMatch($existingArguments)) {
        $saveOption.Replace($existingArguments, { param($match) $saveArgument }, 1)
    } else { "$existingArguments $saveArgument" }
    $launchArguments = [regex]::Replace($launchArguments, '((?:^|\s)-m\s+"?cold_world_game"?)(?=\s+--)', '$1 game')
}

if ($AllowInbound) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Open PowerShell as Administrator to use -AllowInbound.'
    }
    $ruleName = "ColdWorldGame-ZeroTier-$bindAddress-$Port"
    if (-not (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -Name $ruleName -DisplayName "Cold World Game ZeroTier $bindAddress TCP $Port" `
            -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port `
            -LocalAddress $bindAddress -InterfaceAlias 'ZeroTier*' | Out-Null
    }
}

if ($gameIds) {
    # Only signal Ctrl+C if the console is exclusive to this game and its helper.
    $stopHelper = @'
import ctypes
import os
import sys
import time
from ctypes import wintypes

game_ids = {int(value) for value in sys.argv[1:]}
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.FreeConsole()
if kernel.AttachConsole(int(sys.argv[1])):
    processes = (wintypes.DWORD * 16)()
    count = kernel.GetConsoleProcessList(processes, len(processes))
    if 0 < count <= len(processes) and set(processes[:count]) <= game_ids | {os.getpid()}:
        kernel.SetConsoleCtrlHandler(None, True)
        if kernel.GenerateConsoleCtrlEvent(0, 0):
            time.sleep(.3)
    kernel.FreeConsole()
'@
    $oldWorker = Get-Process -Id $gameIds[0] -ErrorAction SilentlyContinue
    if ($oldWorker) {
        $stopHelper | & $python -B - @gameIds
        $null = $oldWorker.WaitForExit(2500)
    }
}
foreach ($gameId in $gameIds) {
    $process = Get-Process -Id $gameId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -InputObject $process
        if (-not $process.WaitForExit(5000)) {
            throw "Previous game process $gameId did not exit."
        }
    }
}

if ($ReuseRunningConfig) {
    $process = Start-Process -FilePath $python -ArgumentList $launchArguments -WorkingDirectory $project -WindowStyle Hidden -PassThru
    $endpoint = 'http://{0}:{1}' -f $bindAddress, $Port
    $request = @{ TimeoutSec = 2; ErrorAction = 'Stop'; UseBasicParsing = $true }
    if ((Get-Command Invoke-RestMethod).Parameters.ContainsKey('NoProxy')) { $request.NoProxy = $true }
    $previous = $null
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if ($process.HasExited) { throw "The game launcher exited with code $($process.ExitCode)." }
        try {
            $health = Invoke-RestMethod -Uri "$endpoint/health" @request
            if ($health.ok -and (Test-Path -LiteralPath $savePath -PathType Leaf)) {
                $catalog = Invoke-RestMethod -Uri "$endpoint/api/info" @request
                [pscustomobject]@{ Server = "$endpoint/"; Healthy = $true; Save = $savePath; Tick = $health.tick; Version = $catalog.terrain.version }
                return
            }
        } catch { $previous = $_.Exception.Message }
        Start-Sleep -Milliseconds 400
    }
    throw "The new save did not pass the game health check. $previous"
}
$serverArguments = @('-B', '-m', 'cold_world_game', 'game', '--host', $bindAddress, '--port', $Port, '--save-path', $savePath, '--log-level', 'WARNING')
if ($PSBoundParameters.ContainsKey('Password')) {
    $serverArguments += @('--password', $Password)
}
if ($Admin) { $serverArguments += @('--admin', $Admin) }
Push-Location -LiteralPath $project
try {
    & $python @serverArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Cold World Game exited with code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
