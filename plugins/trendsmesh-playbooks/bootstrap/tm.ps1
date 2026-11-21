# Runs the TrendsMesh engine (Windows) on the base tier's venv inside the plugin's pixi environment. Arguments pass
# through unchanged.
$tmArgs = @($args)   # kept apart: dot-sourcing install-python.ps1 below sets $args of its own
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
$manifest = Join-Path $root 'env\pixi.toml'
# tm runs on python.org's Python, signed by the Python Software Foundation, in the base tier's venv (issue #123); pixi's
# environment gives it ffmpeg on PATH. Its install at session start failed or did not finish: try once more.
. (Join-Path $PSScriptRoot 'install-python.ps1') -Functions
$venv = Get-TmVenv $data $root 'base'
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-TmVenv $venv)) {
    $why = $null
    $env:CLAUDE_PLUGIN_DATA = $data
    $env:CLAUDE_PLUGIN_ROOT = $root
    try { & (Join-Path $PSScriptRoot 'install-python.ps1') -Tier base *>$null } catch { $why = $_.Exception.Message }
    if (-not (Test-TmVenv $venv)) {
        if (-not $why) { $why = 'unknown' }
        $why = ($why -replace '[\x00-\x1f\x7f]', ' ')
        if ($why.Length -gt 600) { $why = $why.Substring(0, 600) }
        [Console]::Error.WriteLine("tm: the plugin's tools are not set up: its Python did not install into the plugin's data folder, and trying again just now failed too. The reason: $why. Tell the user that reason in plain words: when a site could not be reached, their network, a proxy or firewall, or the app they run Claude in blocks it, and the sites the reason lists must be allowed. Never install Python yourself or change PATH.")
        exit 1
    }
}
# Smart App Control can block a file of the plugin's Python (error 4551, issue #123). tm says so
# itself when it got far enough to run (exit 86 here); any other failure gets one probe in the
# same environment, and a block shows as the number or as Windows' own words for it.
$env:TM_BLOCK_EXIT = '86'
& $pixi run --frozen --manifest-path $manifest -e base $python -m tm @tmArgs
$code = $LASTEXITCODE
Remove-Item Env:TM_BLOCK_EXIT -ErrorAction SilentlyContinue
if ($code -eq 86) { exit 1 }
if ($code -eq 0 -or $code -eq 2) { exit $code }
$ErrorActionPreference = 'Continue'   # 5.1 turns a native command's stderr into an error under 'Stop'
$probe = (& $pixi run --frozen --manifest-path $manifest -e base $python -c 'import ssl,_hashlib,_queue' 2>&1 | ForEach-Object { "$_" }) -join "`n"
if ($LASTEXITCODE -eq 0) { exit $code }
$words = ''
try { $words = ([ComponentModel.Win32Exception]::new(4551).Message).Trim().TrimEnd('.').Trim() } catch { }
$isBlock = $probe -match '(?i)(os error|winerror|error)[^0-9a-z]{0,3}4551([^0-9]|$)'
if (-not $isBlock -and $words -and $words -notmatch '^Unknown error') {
    $isBlock = $probe.IndexOf($words, [StringComparison]::OrdinalIgnoreCase) -ge 0
}
if (-not $isBlock) { exit $code }
$file = if ($probe -match 'while importing ([^\s:]+)') { $Matches[1] } else { 'python.exe' }
$text = "Windows Smart App Control blocked a file of the plugin's Python ({file})."
try {
    $table = [IO.File]::ReadAllText((Join-Path $root 'data\i18n\en.yaml'), [Text.Encoding]::UTF8)
    $m = [regex]::Match($table, '(?m)^\s*smart_app_control:\s*"(.*)"\s*$')
    if ($m.Success) { $text = $m.Groups[1].Value }
} catch { }
[Console]::Error.WriteLine($text.Replace('{file}', $file))
[Console]::Error.WriteLine('For Claude: tell the user these steps in plain words; it is no network or install failure. Never change Windows security settings yourself.')
exit 1
