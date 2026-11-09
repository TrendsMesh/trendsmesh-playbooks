# Installs pixi into <data>\pixi if missing, and points its environments at <data>\envs.
# PIXI_NO_PATH_UPDATE keeps the user's PATH untouched. PIXI_VERSION pins the pixi that CI and the
# lock file were made with (keep it equal to install-pixi.sh and pixi-version in CI).
# Throws, with the reason, when pixi.exe is not there afterwards.
$ErrorActionPreference = 'Stop'
$data = $env:CLAUDE_PLUGIN_DATA
if (-not $data) { throw 'CLAUDE_PLUGIN_DATA is not set' }
$pixiHome = Join-Path $data 'pixi'
$exe = Join-Path $pixiHome 'bin\pixi.exe'
New-Item -ItemType Directory -Force -Path $pixiHome | Out-Null

if (-not (Test-Path $exe)) {
    $env:PIXI_HOME = $pixiHome
    $env:PIXI_NO_PATH_UPDATE = '1'
    $env:PIXI_VERSION = 'v0.84.1'
    # Windows PowerShell 5.1 may not offer TLS 1.2 by default; pixi.sh and GitHub need it.
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    try {
        $installer = Invoke-RestMethod -Uri 'https://pixi.sh/install.ps1' -TimeoutSec 60
    } catch {
        throw "could not download the pixi installer from pixi.sh (no internet connection, or a proxy or firewall blocks it): $($_.Exception.Message)"
    }
    if (-not $installer) { throw 'the pixi installer downloaded empty' }
    # The official installer script; its output goes to the host, not into Claude's context.
    Invoke-Expression $installer *>$null
    if (-not (Test-Path $exe)) { throw "pixi.exe is not in $pixiHome\bin after its installer ran" }
}

$envs = ((Join-Path $data 'envs') -replace '\\', '/') -replace '"', '\"'
[System.IO.File]::WriteAllText((Join-Path $pixiHome 'config.toml'), "detached-environments = `"$envs`"`n")
