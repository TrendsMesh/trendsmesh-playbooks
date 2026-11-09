# Runs the TrendsMesh engine in the plugin's pixi environment. Arguments pass through unchanged.
$root = $env:TM_PLUGIN_ROOT
$data = $env:TM_PLUGIN_DATA
if (-not $root -or -not $data) {
    $pj = Join-Path $env:USERPROFILE '.trendsmesh\paths.json'
    if (Test-Path $pj) {
        $p = Get-Content -Raw -Encoding UTF8 $pj | ConvertFrom-Json
        if (-not $root) { $root = $p.plugin_root }
        if (-not $data) { $data = $p.plugin_data }
    }
}
if (-not $root -or -not $data) {
    [Console]::Error.WriteLine('tm: the plugin has not set itself up yet. Start a new Claude Code session, then try again.')
    exit 1
}
$env:TM_PLUGIN_ROOT = $root
$env:TM_PLUGIN_DATA = $data
$env:PIXI_HOME = Join-Path $data 'pixi'
$env:PIXI_NO_PATH_UPDATE = '1'
$pixi = Join-Path $env:PIXI_HOME 'bin\pixi.exe'
if (-not (Test-Path $pixi)) {
    [Console]::Error.WriteLine('tm: the plugin''s tools are not set up: pixi is missing from the plugin''s data folder (its download at session start failed: no internet connection, a proxy or firewall, or a cut-off download). Never install pixi yourself or change PATH: run /trendsmesh-playbooks:doctor, and ask the user to check the connection and start a new Claude Code session, which installs it again.')
    exit 1
}
$cfg = Join-Path $env:PIXI_HOME 'config.toml'
if (-not (Test-Path $cfg)) {
    New-Item -ItemType Directory -Force -Path $env:PIXI_HOME | Out-Null
    $envs = (Join-Path $data 'envs') -replace '\\', '/'
    [System.IO.File]::WriteAllText($cfg, "detached-environments = `"$envs`"`n")
}
& $pixi run --frozen --manifest-path (Join-Path $root 'env\pixi.toml') -e base python -m tm @args
exit $LASTEXITCODE
