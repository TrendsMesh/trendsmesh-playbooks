# SessionStart hook (Windows). A no-op on macOS and Linux, where session-start.sh does the work.
# Never prints a secret value.
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSEdition -eq 'Core' -and -not $IsWindows) { exit 0 }
if ($env:OS -ne 'Windows_NT') { exit 0 }

try {
    # The hook's output is UTF-8 (a run name can hold Polish letters), and so is what tm prints.
    try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }
    $root = if ($env:CLAUDE_PLUGIN_ROOT) { $env:CLAUDE_PLUGIN_ROOT } else { Split-Path -Parent $PSScriptRoot }
    $data = $env:CLAUDE_PLUGIN_DATA
    if (-not $data) { exit 0 }
    Write-Output 'TrendsMesh playbooks: never search for, read or show the Replicate or ElevenLabs keys, not even masked; tm doctor says whether each is set.'
    New-Item -ItemType Directory -Force -Path $data | Out-Null

    # 1. pixi. A failure is said in one line at the end, after the paths are written, so that
    #    `tm` can say what is wrong too.
    $pixi = Join-Path $data 'pixi\bin\pixi.exe'
    try { & (Join-Path $PSScriptRoot 'install-pixi.ps1') *>$null } catch { }
    $pixiOk = Test-Path $pixi

    # 2. paths.json
    $tmDir = Join-Path $env:USERPROFILE '.trendsmesh'
    New-Item -ItemType Directory -Force -Path $tmDir | Out-Null
    $json = [ordered]@{ plugin_root = $root; plugin_data = $data; pixi = $pixi } | ConvertTo-Json
    [System.IO.File]::WriteAllText((Join-Path $tmDir 'paths.json'), $json)

    # 3. make the folders visible to Bash tool calls (Git Bash syntax, forward slashes). UTF-8
    #    without a BOM and LF line ends on 5.1 and 7 alike: Add-Content on 5.1 writes the ANSI code
    #    page, which turns a user folder with a Polish letter into a path Git Bash cannot find.
    if ($env:CLAUDE_ENV_FILE) {
        $r = ($root -replace '\\', '/') -replace "'", "'\''"
        $d = ($data -replace '\\', '/') -replace "'", "'\''"
        $text = "export TM_PLUGIN_ROOT='$r'`nexport TM_PLUGIN_DATA='$d'`n"
        [IO.File]::AppendAllText($env:CLAUDE_ENV_FILE, $text, (New-Object System.Text.UTF8Encoding $false))
    }

    # 4. secrets.env, readable by the current user only
    $secrets = Join-Path $data 'secrets.env'
    if (Test-Path $secrets) { Remove-Item -Force $secrets }
    New-Item -ItemType File -Path $secrets | Out-Null
    # Drop inherited permissions, then grant the current user alone.
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    & icacls.exe $secrets /inheritance:r /grant:r "*${sid}:(R,W)" *>$null
    if ($LASTEXITCODE -ne 0) {
        # Never leave secrets in a file with inherited permissions.
        Remove-Item -Force $secrets
        [Console]::Error.WriteLine('trendsmesh-playbooks: could not restrict secrets.env to your user; keys not saved.')
        exit 0
    }
    $lines = @()
    if ($env:CLAUDE_PLUGIN_OPTION_REPLICATE_API_TOKEN -and $env:CLAUDE_PLUGIN_OPTION_REPLICATE_API_TOKEN -notmatch "[\r\n]") {
        $lines += "REPLICATE_API_TOKEN=$($env:CLAUDE_PLUGIN_OPTION_REPLICATE_API_TOKEN)"
    }
    if ($env:CLAUDE_PLUGIN_OPTION_ELEVENLABS_API_KEY -and $env:CLAUDE_PLUGIN_OPTION_ELEVENLABS_API_KEY -notmatch "[\r\n]") {
        $lines += "ELEVENLABS_API_KEY=$($env:CLAUDE_PLUGIN_OPTION_ELEVENLABS_API_KEY)"
    }
    if ($lines.Count -gt 0) {
        [System.IO.File]::WriteAllText($secrets, ($lines -join "`n") + "`n")
    }

    if (-not $pixiOk) {
        Write-Output "TrendsMesh playbooks: its tools could not be set up, because pixi did not install into the plugin's data folder (no internet connection, a proxy or firewall, or a cut-off download), so tm cannot run. Never install pixi yourself or change PATH or global packages: run /trendsmesh-playbooks:doctor, and ask the user to check the connection and start a new session."
        exit 0
    }

    # 5. what is due: `tm due --quiet` prints one plain line per measurement due and nothing
    #    else. No inline Python: 5.1 strips the quotes of a native argument. Any failure means
    #    "nothing due". 'Continue', as 5.1 turns a native command's stderr into an error under 'Stop'.
    $env:PIXI_HOME = Join-Path $data 'pixi'
    $env:PIXI_NO_PATH_UPDATE = '1'
    $env:TM_PLUGIN_ROOT = $root
    $env:TM_PLUGIN_DATA = $data
    $manifest = Join-Path $root 'env\pixi.toml'
    $ErrorActionPreference = 'Continue'
    $due = & $pixi run --as-is --manifest-path $manifest -e base python -m tm due --quiet 2>$null
    if ($LASTEXITCODE -eq 0 -and $due) { $due | ForEach-Object { Write-Output $_ } }
} catch {
    # A hook must never break the session.
}
exit 0
