[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ipaddress] $Address,

    [ValidateRange(1, 65535)]
    [int] $Port = 12942,

    [ValidateNotNullOrEmpty()]
    [string] $Password,

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

$processes = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -match '\s-m\s+"?cold_world_game"?(?:\s|$)' })
$launchers = @($processes | Where-Object { $_.ExecutablePath -eq $python })
$launcherIds = @($launchers | ForEach-Object { $_.ProcessId })
$workers = @($processes | Where-Object { $_.ParentProcessId -in $launcherIds })
$gameIds = @($workers + $launchers | ForEach-Object { $_.ProcessId })
$otherListener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -in @($bindAddress, '0.0.0.0') -and $_.OwningProcess -notin $gameIds }
if ($otherListener) {
    throw "TCP port $Port at $bindAddress is already in use by another process."
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

foreach ($gameId in $gameIds) {
    $process = Get-Process -Id $gameId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -InputObject $process
        if (-not $process.WaitForExit(5000)) {
            throw "Previous game process $gameId did not exit."
        }
    }
}

$saveDirectory = "saves\zerotier-$(Get-Date -Format 'yyyyMMdd-HHmmss')-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
$savePath = Join-Path $project "$saveDirectory\world.sqlite3"
$serverArguments = @('-B', '-m', 'cold_world_game', 'game', '--host', $bindAddress, '--port', $Port, '--save-path', $savePath, '--log-level', 'WARNING')
if ($PSBoundParameters.ContainsKey('Password')) {
    $serverArguments += @('--password', $Password)
}
Push-Location -LiteralPath $project
try {
    & $python @serverArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Cold World Game exited with code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
