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
    # Its install at session start failed: try once more, so a new session is not needed.
    $why = $null
    $env:CLAUDE_PLUGIN_DATA = $data
    try { & (Join-Path $PSScriptRoot 'install-pixi.ps1') *>$null } catch { $why = $_.Exception.Message }
    if (-not (Test-Path $pixi)) {
        if (-not $why) { $why = 'unknown' }
        $why = ($why -replace '[\x00-\x1f\x7f]', ' ')
        if ($why.Length -gt 600) { $why = $why.Substring(0, 600) }
        [Console]::Error.WriteLine("tm: the plugin's tools are not set up: pixi did not install into the plugin's data folder, and trying again just now failed too. The reason: $why. Tell the user that reason in plain words: when a site could not be reached, their network, a proxy or firewall, or the app they run Claude in blocks it, and the sites the reason lists must be allowed. Never install pixi yourself or change PATH.")
        exit 1
    }
}
$cfg = Join-Path $env:PIXI_HOME 'config.toml'
if (-not (Test-Path $cfg)) {
    New-Item -ItemType Directory -Force -Path $env:PIXI_HOME | Out-Null
    $envs = (Join-Path $data 'envs') -replace '\\', '/'
    [System.IO.File]::WriteAllText($cfg, "detached-environments = `"$envs`"`n")
}
& $pixi run --frozen --manifest-path (Join-Path $root 'env\pixi.toml') -e base python -m tm @args
exit $LASTEXITCODE
