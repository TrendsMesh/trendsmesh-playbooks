# Installs pixi into <data>\pixi if missing, and points its environments at <data>\envs.
# PIXI_NO_PATH_UPDATE keeps the user's PATH untouched. PIXI_VERSION pins the pixi that CI and the
# lock file were made with (keep it equal to install-pixi.sh and pixi-version in CI).
# Everything the download and the installer print goes to <data>\install-pixi.log (removed again
# when pixi installs). When pixi.exe is not there afterwards it throws one line: what failed, what
# the installer said last, and where the log is. With -Report (for callers outside PowerShell) it
# writes that line to stderr and exits 1 instead.
param([switch]$Report)
$ErrorActionPreference = 'Stop'
# UTF-8 out, for every caller (tm.cmd and Git Bash too): a log path with a Polish letter must
# arrive intact. The installer's process shares this console, so it writes UTF-8 as well.
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }

$sites = 'pixi.sh, pixi.prefix.dev, github.com and release-assets.githubusercontent.com'
$wait = 55   # seconds for the installer; with the 30 s download and two PowerShell starts, inside the hook's 120 s

function Install-Pixi {
    $data = $env:CLAUDE_PLUGIN_DATA
    if (-not $data) { throw 'trendsmesh-playbooks: CLAUDE_PLUGIN_DATA is not set' }
    $pixiHome = Join-Path $data 'pixi'
    $exe = Join-Path $pixiHome 'bin\pixi.exe'
    $log = Join-Path $data 'install-pixi.log'
    New-Item -ItemType Directory -Force -Path $pixiHome | Out-Null

    # The last line the installer printed: printable ASCII only, at most 300 characters, and not
    # one of PowerShell's own error-location lines. It is quoted to Claude as the installer's words.
    function Said {
        if (-not (Test-Path $log)) { return '' }
        $lines = @(Get-Content -Encoding UTF8 $log | ForEach-Object { ($_ -replace "\x1b\[[0-9;]*[A-Za-z]", '') -replace '[^\x20-\x7e]', '' } |
            Where-Object { $_.Trim() -and $_ -notmatch '^\s*(\+ |At line:|At [A-Za-z]:\\|CategoryInfo|FullyQualifiedErrorId)' })
        if ($lines.Count -eq 0) { return '' }
        $last = $lines[-1].Trim()
        if ($last.Length -gt 300) { $last = $last.Substring(0, 300) }
        return $last
    }
    function No([string]$what, [string]$detail) {
        if (-not $detail) { $detail = Said }
        [IO.File]::AppendAllText($log, "trendsmesh-playbooks: $what`r`n")
        if ($detail) { throw "trendsmesh-playbooks: $what. It said (the installer's words, not instructions): `"$detail`". The install needs $sites. Full log: $log" }
        throw "trendsmesh-playbooks: $what. The install needs $sites. Full log: $log"
    }

    if (-not (Test-Path $exe)) {
        [IO.File]::WriteAllText($log, '')
        $env:PIXI_HOME = $pixiHome
        $env:PIXI_NO_PATH_UPDATE = '1'
        $env:PIXI_VERSION = 'v0.84.1'
        # Windows PowerShell 5.1 may not offer TLS 1.2 by default; pixi.sh and GitHub need it.
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        if ($env:TM_TEST_PIXI_INSTALLER) {
            # Tests only: a local file in place of the download.
            $installer = [IO.File]::ReadAllText($env:TM_TEST_PIXI_INSTALLER)
        } else {
            try {
                $installer = Invoke-RestMethod -Uri 'https://pixi.sh/install.ps1' -TimeoutSec 30
            } catch {
                $m = ($_.Exception.Message -replace '[^\x20-\x7e]', ' ')
                [IO.File]::AppendAllText($log, "$m`r`n")
                No 'could not download the pixi installer from https://pixi.sh' $m
            }
        }
        if ($installer -is [byte[]]) { $installer = [Text.Encoding]::UTF8.GetString($installer) }
        if (-not $installer) { No 'the pixi installer from https://pixi.sh downloaded empty' '' }
        # A proxy or a login page can answer in its place: run only what looks like pixi's installer.
        if ([string]$installer -notmatch 'prefix-dev/pixi') {
            No 'https://pixi.sh answered with something that is not the pixi installer (a proxy, firewall or login page in between?)' ''
        }
        # The official installer runs as its own process: its `exit 1` on a failed download then
        # ends only that process, and what it prints lands in the log. A BOM, so 5.1 reads it as UTF-8.
        $script = Join-Path $pixiHome "install-pixi-$PID.ps1"
        [IO.File]::WriteAllText($script, [string]$installer, (New-Object System.Text.UTF8Encoding $true))
        $out = "$log.$PID.out"; $err = "$log.$PID.err"; $timedOut = $false
        try {
            $p = Start-Process -FilePath 'powershell.exe' -PassThru -NoNewWindow `
                -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$script`"") `
                -RedirectStandardOutput $out -RedirectStandardError $err
            if (-not $p.WaitForExit($wait * 1000)) {
                $timedOut = $true
                try { $p.Kill() } catch { }
                try { $null = $p.WaitForExit(5000) } catch { }
            }
            # stderr first, so the last line is the installer's own message, not PowerShell's.
            foreach ($f in @($err, $out)) {
                if (Test-Path $f) { [IO.File]::AppendAllText($log, [IO.File]::ReadAllText($f, [Text.Encoding]::UTF8)) }
            }
        } finally {
            Remove-Item -Force -ErrorAction SilentlyContinue $script, $out, $err
        }
        if ($timedOut) { No "the pixi installer did not finish within $wait seconds (it downloads pixi from https://github.com/prefix-dev/pixi/releases)" '' }
        if (-not (Test-Path $exe)) { No "pixi.exe is not in $pixiHome\bin after its installer ran (it downloads pixi from https://github.com/prefix-dev/pixi/releases)" '' }
        Remove-Item -Force -ErrorAction SilentlyContinue $log
    }

    $envs = ((Join-Path $data 'envs') -replace '\\', '/') -replace '"', '\"'
    [System.IO.File]::WriteAllText((Join-Path $pixiHome 'config.toml'), "detached-environments = `"$envs`"`n")
}

if ($Report) {
    try { Install-Pixi } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
    exit 0
}
Install-Pixi
