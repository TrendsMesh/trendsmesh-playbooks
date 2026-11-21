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

    $pixi = Join-Path $data 'pixi\bin\pixi.exe'

    # 1. paths.json (first, so that tm finds the plugin even when this hook is cut off during the
    #    pixi download below)
    $tmDir = Join-Path $env:USERPROFILE '.trendsmesh'
    New-Item -ItemType Directory -Force -Path $tmDir | Out-Null
    $json = [ordered]@{ plugin_root = $root; plugin_data = $data; pixi = $pixi } | ConvertTo-Json
    [System.IO.File]::WriteAllText((Join-Path $tmDir 'paths.json'), $json)

    # 2. make the folders visible to Bash tool calls (Git Bash syntax, forward slashes). UTF-8
    #    without a BOM and LF line ends on 5.1 and 7 alike: Add-Content on 5.1 writes the ANSI code
    #    page, which turns a user folder with a Polish letter into a path Git Bash cannot find.
    if ($env:CLAUDE_ENV_FILE) {
        $r = ($root -replace '\\', '/') -replace "'", "'\''"
        $d = ($data -replace '\\', '/') -replace "'", "'\''"
        $text = "export TM_PLUGIN_ROOT='$r'`nexport TM_PLUGIN_DATA='$d'`n"
        [IO.File]::AppendAllText($env:CLAUDE_ENV_FILE, $text, (New-Object System.Text.UTF8Encoding $false))
    }

    # 3. pixi. What the installer prints goes to its log; on a failure its one-line reason is
    #    kept and said at the end. tm tries again later.
    $why = $null
    try { & (Join-Path $PSScriptRoot 'install-pixi.ps1') *>$null } catch { $why = $_.Exception.Message }
    $pixiOk = Test-Path $pixi

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
        if (-not $why) { $why = 'unknown' }
        $why = ($why -replace '[\x00-\x1f\x7f]', ' ')
        if ($why.Length -gt 600) { $why = $why.Substring(0, 600) }
        Write-Output "TrendsMesh playbooks: its tools could not be set up, because pixi did not install into the plugin's data folder, so tm cannot run yet. The reason: $why. Never install pixi yourself or change PATH or global packages. Running tm tries the install again; /trendsmesh-playbooks:doctor does that and tells the user the reason above in plain words."
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
    #    Windows Smart App Control blocking the plugin's Python (error 4551, issue #123) is the one
    #    failure that is said: in one line, from what tm or pixi wrote to stderr.
    $ErrorActionPreference = 'Continue'
    $errFile = [IO.Path]::GetTempFileName()
    $due = & $pixi run --as-is --manifest-path $manifest -e base python -m tm due --quiet 2>$errFile
    $rc = $LASTEXITCODE
    $err = ''
    try { $err = [IO.File]::ReadAllText($errFile) } catch { }
    Remove-Item -LiteralPath $errFile -Force -ErrorAction SilentlyContinue
    if ($rc -eq 0) {
        if ($due) { $due | ForEach-Object { Write-Output $_ } }
    } else {
        $words = ''
        try { $words = ([ComponentModel.Win32Exception]::new(4551).Message).Trim().TrimEnd('.').Trim() } catch { }
        $isBlock = $err -match '(?i)Smart App Control|(os error|winerror|error)[^0-9a-z]{0,3}4551([^0-9]|$)'
        if (-not $isBlock -and $words) { $isBlock = $err.IndexOf($words, [StringComparison]::OrdinalIgnoreCase) -ge 0 }
        if ($isBlock) {
            $file = 'python.exe'
            if ($err -match "plugin's Python \(([^)]*)\)") { $file = $Matches[1] }
            elseif ($err -match 'while importing ([^\s:]+)') { $file = $Matches[1] }
            $steps = ''
            try {
                $table = [IO.File]::ReadAllText((Join-Path $root 'data\i18n\en.yaml'), [Text.Encoding]::UTF8)
                $m = [regex]::Match($table, '(?m)^\s*smart_app_control:\s*"(.*)"\s*$')
                if ($m.Success) { $steps = $m.Groups[1].Value.Replace('{file}', $file) }
            } catch { }
            Write-Output "TrendsMesh playbooks: Windows Smart App Control blocked a file of the plugin's Python ($file), so tm cannot run. Tell the user the steps from tm's message in plain words; never change Windows security settings yourself. tm's message: $steps"
        }
    }
} catch {
    # A hook must never break the session.
}
exit 0
