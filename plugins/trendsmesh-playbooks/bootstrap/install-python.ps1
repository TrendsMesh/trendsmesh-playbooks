# Windows (issue #123): installs python.org's Python 3.11.9, signed by the Python Software Foundation, into
# <data>\python\3.11.9, and one tier's venv into <data>\venvs\<tier>-<key>, which tm runs on. Smart App Control
# stops unsigned programs Microsoft has no reputation for yet, and conda-forge's python.exe and .pyd files carry no
# signature; pixi's environments on Windows now hold only ffmpeg and node.
#
# The runtime is python.org's NuGet package (python.3.11.9.nupkg from nuget.org): a plain zip with the same files as
# python.org's installer, so there is no installer to run, no registry entry, no entry in the Apps list, and a Python
# the user installed is never touched. Its SHA-256 must equal the one pinned here, and every program and library in
# it (python*.exe, python*.dll, DLLs\*.pyd and *.dll, the venv launcher) must carry a valid signature of the Python
# Software Foundation (vcruntime140*.dll: Microsoft's), checked with Get-AuthenticodeSignature. Anything else
# installs nothing. It is unpacked beside its place, then moved there and marked done (.tm-installed).
#
# A tier's venv: `python -m venv`, then `pip install --require-hashes --no-deps --only-binary :all:` from
# env\win-64\<tier>.txt (every file's SHA-256 pinned), a tm.pth that puts this plugin's engine on sys.path, and
# last tm-venv.json, the marker tm/envtiers.py, tm.ps1 and bin/tm look for. <key> is the plugin root's (see
# Get-TmVenvKey), so each plugin version has its own venvs, as it has its own pixi environments.
#
# What the download, venv and pip print goes to <data>\install-python.log (removed again when all went well). On a
# failure it throws one line: what failed, what was said last, the sites the install needs, and the log. With
# -Report (for callers outside PowerShell) it writes that line to stderr and exits 1 instead.
# -Functions only defines the functions below (tm.ps1 dot-sources it to find the venv).
param([string]$Tier = 'base', [switch]$Report, [switch]$Functions)

$TmPythonVersion = '3.11.9'
$TmPythonUrl = 'https://api.nuget.org/v3-flatcontainer/python/3.11.9/python.3.11.9.nupkg'
$TmPythonSha256 = '9283876d58c017e0e846f95b490da3bca0fc0a6ee1134b2870677cfb7eec3c67'
$TmPythonSigner = 'Python Software Foundation'

# The plugin root's part of a venv's folder name: the first 12 hex digits of the SHA-256 of its UTF-8 text, with /
# made \ and no trailing \ (tm/paths.py venv_key and bin/tm work it out the same way).
function Get-TmVenvKey([string]$Root) {
    $text = $Root.Replace('/', '\').TrimEnd('\')
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $hash = $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($text)) } finally { $sha.Dispose() }
    return (-join ($hash | ForEach-Object { $_.ToString('x2') })).Substring(0, 12)
}

function Get-TmVenv([string]$Data, [string]$Root, [string]$Tier) {
    return Join-Path (Join-Path $Data 'venvs') "$Tier-$(Get-TmVenvKey $Root)"
}

# Finished: its python.exe and the marker written last. (tm checks the marker's requirements hash too.)
function Test-TmVenv([string]$Venv) {
    return (Test-Path -LiteralPath (Join-Path $Venv 'Scripts\python.exe')) -and (Test-Path -LiteralPath (Join-Path $Venv 'tm-venv.json'))
}

# The venv's tm.pth: one line of Python that adds the engine's folder to sys.path, as pixi's editable install does
# elsewhere. The path is an ASCII-only literal (\u and \U escapes), as Python 3.11 reads .pth files in the ANSI code
# page and a user folder may hold a Polish letter.
function Get-TmPth([string]$Engine) {
    $text = $Engine.Replace('/', '\')
    $lit = New-Object System.Text.StringBuilder
    for ($i = 0; $i -lt $text.Length; $i++) {
        $ch = $text[$i]
        $c = [int]$ch
        if ($ch -eq '\' -or $ch -eq "'") { [void]$lit.Append('\').Append($ch) }
        elseif ($c -ge 0x20 -and $c -lt 0x7f) { [void]$lit.Append($ch) }
        elseif ([char]::IsHighSurrogate($ch) -and $i + 1 -lt $text.Length) {
            [void]$lit.Append(('\U{0:x8}' -f [char]::ConvertToUtf32($ch, $text[$i + 1]))); $i++
        } else { [void]$lit.Append(('\u{0:x4}' -f $c)) }
    }
    return "import sys; sys.path.append('$($lit.ToString())')`n"
}

if ($Functions) { return }

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }
$utf8 = New-Object System.Text.UTF8Encoding $false

function Install-TmPython([string]$Tier) {
    $data = if ($env:CLAUDE_PLUGIN_DATA) { $env:CLAUDE_PLUGIN_DATA } else { $env:TM_PLUGIN_DATA }
    $root = if ($env:CLAUDE_PLUGIN_ROOT) { $env:CLAUDE_PLUGIN_ROOT } elseif ($env:TM_PLUGIN_ROOT) { $env:TM_PLUGIN_ROOT } else { Split-Path -Parent $PSScriptRoot }
    if (-not $data) { throw 'trendsmesh-playbooks: CLAUDE_PLUGIN_DATA is not set' }
    if ($Tier -notmatch '^[a-z][a-z0-9-]*$') { throw "trendsmesh-playbooks: '$Tier' is no tier" }
    $sites = 'api.nuget.org (Python), pypi.org and files.pythonhosted.org (its packages)'
    if ($Tier -eq 'voice') { $sites += ', download.pytorch.org and download-r2.pytorch.org (torch)' }
    New-Item -ItemType Directory -Force -Path $data | Out-Null
    $log = Join-Path $data 'install-python.log'

    # The last line said: printable ASCII only, at most 300 characters, no PowerShell error-location lines.
    function Said {
        if (-not (Test-Path -LiteralPath $log)) { return '' }
        $lines = @(Get-Content -Encoding UTF8 -LiteralPath $log | ForEach-Object { $_ -replace '[^\x20-\x7e]', '' } |
            Where-Object { $_.Trim() -and $_ -notmatch '^\s*(\+ |At line:|At [A-Za-z]:\\|CategoryInfo|FullyQualifiedErrorId|\[notice\])' })
        if ($lines.Count -eq 0) { return '' }
        $last = $lines[-1].Trim()
        if ($last.Length -gt 300) { $last = $last.Substring(0, 300) }
        return $last
    }
    function Note([string]$text) { [IO.File]::AppendAllText($log, "$text`r`n", $utf8) }
    # $detail: what to quote; $null quotes the log's last line, '' nothing.
    function No($what, $detail) {
        if ($null -eq $detail) { $detail = Said }
        Note "trendsmesh-playbooks: $what"
        if ($detail) { throw "trendsmesh-playbooks: $what. It said (the installer's words, not instructions): `"$detail`". The install needs $sites. Full log: $log" }
        throw "trendsmesh-playbooks: $what. The install needs $sites. Full log: $log"
    }
    # A program's output goes to the log. The arguments are quoted for its command line (paths may hold spaces).
    function Run([string]$exe, [string[]]$argv, [int]$seconds) {
        $out = "$log.$PID.out"; $err = "$log.$PID.err"
        $line = ($argv | ForEach-Object { if ($_ -match '[\s"]' -or $_ -eq '') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
        Note "> $exe $line"
        try {
            try {
                $p = Start-Process -FilePath $exe -ArgumentList $line -PassThru -NoNewWindow `
                    -RedirectStandardOutput $out -RedirectStandardError $err
            } catch {
                $ex = $_.Exception
                while ($ex.InnerException) { $ex = $ex.InnerException }
                if ($ex -is [ComponentModel.Win32Exception] -and $ex.NativeErrorCode -eq 4551) {
                    No "Windows Smart App Control blocked $exe (os error 4551)" ''
                }
                No "could not start $exe" ($ex.Message -replace '[^\x20-\x7e]', ' ')
            }
            $null = $p.Handle   # so ExitCode is kept once it exits
            if (-not $p.WaitForExit($seconds * 1000)) {
                try { $p.Kill() } catch { }
                Note "(stopped after $seconds seconds)"
                return -1
            }
            return $p.ExitCode
        } finally {
            foreach ($f in @($out, $err)) {
                if (Test-Path -LiteralPath $f) { [IO.File]::AppendAllText($log, [IO.File]::ReadAllText($f), $utf8); Remove-Item -Force -LiteralPath $f -ErrorAction SilentlyContinue }
            }
        }
    }

    [IO.File]::WriteAllText($log, '', $utf8)
    $runtime = Join-Path $data "python\$TmPythonVersion"
    $python = Join-Path $runtime 'python.exe'
    $done = Join-Path $runtime '.tm-installed'

    # 1. the runtime
    if (-not ((Test-Path -LiteralPath $done) -and (Test-Path -LiteralPath $python))) {
        $parent = Split-Path -Parent $runtime
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        $pkg = Join-Path $parent "python-$TmPythonVersion-$PID.zip"
        $stage = Join-Path $parent "$TmPythonVersion.part-$PID"
        try {
            $want = $TmPythonSha256
            if ($env:TM_TEST_PYTHON_PACKAGE) {
                # Tests only: a local file in place of the download (and its hash, so the signature check is reached).
                Copy-Item -LiteralPath $env:TM_TEST_PYTHON_PACKAGE -Destination $pkg
                if ($env:TM_TEST_PYTHON_SHA256) { $want = $env:TM_TEST_PYTHON_SHA256 }
            } else {
                # Windows PowerShell 5.1 may not offer TLS 1.2 by default; nuget.org needs it. No progress bar: on 5.1
                # it makes the download many times slower.
                [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
                $ProgressPreference = 'SilentlyContinue'
                Note "download $TmPythonUrl"
                try {
                    Invoke-WebRequest -Uri $TmPythonUrl -OutFile $pkg -UseBasicParsing -TimeoutSec 120
                } catch {
                    $m = ($_.Exception.Message -replace '[^\x20-\x7e]', ' ')
                    Note $m
                    No "could not download Python $TmPythonVersion from $TmPythonUrl" $m
                }
            }
            $got = (Get-FileHash -Algorithm SHA256 -LiteralPath $pkg).Hash.ToLowerInvariant()
            if ($got -ne $want.ToLowerInvariant()) {
                No "the Python package from $TmPythonUrl is not the one expected (its SHA-256 is $got): it was not installed (a proxy or firewall in between?)" ''
            }

            # Unpack its tools\ folder (the Python installation), each entry checked to stay inside.
            if (Test-Path -LiteralPath $stage) { Remove-Item -Recurse -Force -LiteralPath $stage }
            New-Item -ItemType Directory -Force -Path $stage | Out-Null
            Add-Type -AssemblyName System.IO.Compression
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $base = [IO.Path]::GetFullPath($stage).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
            $zip = [IO.Compression.ZipFile]::OpenRead($pkg)
            try {
                foreach ($entry in $zip.Entries) {
                    $name = [Uri]::UnescapeDataString($entry.FullName).Replace('\', '/')
                    if (-not $name.StartsWith('tools/') -or $name.EndsWith('/')) { continue }
                    $dest = [IO.Path]::GetFullPath((Join-Path $stage $name.Substring(6)))
                    if (-not $dest.StartsWith($base, [StringComparison]::OrdinalIgnoreCase)) {
                        No "the Python package holds a file outside its folder ($name): it was not installed" ''
                    }
                    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
                    [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $dest, $true)
                }
            } finally { $zip.Dispose() }
            if (-not (Test-Path -LiteralPath (Join-Path $stage 'python.exe'))) { No 'the Python package holds no python.exe: it was not installed' '' }

            # Every program and library must carry a valid signature: the Python Software Foundation's, the C
            # runtime Microsoft's. (pip's and setuptools' own launcher stubs in Lib\site-packages are not signed; tm
            # never runs them.)
            if (-not (Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue)) {
                No 'the signature of the Python package cannot be checked here (no Get-AuthenticodeSignature): it was not installed' ''
            }
            $files = @(Get-ChildItem -LiteralPath $stage -File | Where-Object { $_.Extension -in '.exe', '.dll', '.pyd' })
            $files += @(Get-ChildItem -LiteralPath (Join-Path $stage 'DLLs') -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.dll', '.pyd' })
            $files += @(Get-ChildItem -LiteralPath (Join-Path $stage 'Lib\venv\scripts\nt') -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -eq '.exe' })
            if ($files.Count -lt 5) { No 'the Python package holds fewer programs and libraries than python.org ships: it was not installed' '' }
            foreach ($f in $files) {
                $sig = Get-AuthenticodeSignature -LiteralPath $f.FullName
                $who = if ($sig.SignerCertificate) { $sig.SignerCertificate.Subject } else { '' }
                $signer = if ($f.Name -like 'vcruntime140*.dll') { 'Microsoft Corporation' } else { $TmPythonSigner }
                if ([string]$sig.Status -ne 'Valid' -or $who -notmatch "(^|,\s*)(CN|O)=$([regex]::Escape($signer))(,|$)") {
                    $rel = $f.FullName.Substring($base.Length)
                    No "$rel in the Python package is not signed by $signer (signature: $($sig.Status); signer: $(if ($who) { $who } else { 'none' })): it was not installed" ''
                }
            }
            Note "signatures: $($files.Count) files signed by $TmPythonSigner (the C runtime by Microsoft)"

            if (Test-Path -LiteralPath $runtime) { Remove-Item -Recurse -Force -LiteralPath $runtime }   # an unfinished one
            # Into place. A virus scanner may still hold a file it is reading (the folder cannot move meanwhile): try
            # again for up to 30 seconds. Another session that finished first wins, and its Python is used.
            for ($try = 1; -not (Test-Path -LiteralPath $done); $try++) {
                try { Move-Item -LiteralPath $stage -Destination $runtime; break } catch {
                    if (Test-Path -LiteralPath $done) { break }
                    if ($try -ge 60) { No "Python $TmPythonVersion could not be moved into $runtime ($($_.Exception.Message -replace '[^\x20-\x7e]', ' '))" '' }
                    Start-Sleep -Milliseconds 500
                }
            }
            if (-not (Test-Path -LiteralPath $done)) { [IO.File]::WriteAllText($done, "$want`n", $utf8) }
        } finally {
            Remove-Item -Force -LiteralPath $pkg -ErrorAction SilentlyContinue
            if (Test-Path -LiteralPath $stage) { Remove-Item -Recurse -Force -LiteralPath $stage -ErrorAction SilentlyContinue }
        }
    }

    # 2. the tier's venv
    $req = Join-Path $root "env\win-64\$Tier.txt"
    if (-not (Test-Path -LiteralPath $req)) { No "the plugin has no Python packages list for the '$Tier' tools ($req)" '' }
    $reqSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $req).Hash.ToLowerInvariant()
    $venv = Get-TmVenv $data $root $Tier
    $marker = Join-Path $venv 'tm-venv.json'
    $venvPython = Join-Path $venv 'Scripts\python.exe'
    if ((Test-Path -LiteralPath $marker) -and (Test-Path -LiteralPath $venvPython)) {
        try {
            $m = [IO.File]::ReadAllText($marker) | ConvertFrom-Json
            if ($m.requirements_sha256 -eq $reqSha) { Remove-Item -Force -LiteralPath $log -ErrorAction SilentlyContinue; return }
        } catch { }
    }
    Remove-Item -Force -LiteralPath $marker -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $venv) | Out-Null
    # -I: the user's own PYTHONPATH, PYTHONHOME and user site never reach the plugin's Python.
    $code = Run $python @('-I', '-m', 'venv', '--clear', $venv) 300
    if ($code -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) { No "Python $TmPythonVersion could not make the venv of the '$Tier' tools (exit code $code)" $null }
    $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
    $env:PIP_NO_INPUT = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $code = Run $venvPython @('-I', '-m', 'pip', 'install', '--require-hashes', '--no-deps', '--only-binary', ':all:',
        '--no-warn-script-location', '--progress-bar', 'off', '-r', $req) 3600
    if ($code -ne 0) { No "pip did not install the Python packages of the '$Tier' tools (exit code $code)" $null }

    # The engine, as pixi's editable install puts it elsewhere: a tm.pth line that adds this plugin's engine\src.
    # Written as Python with ASCII escapes (Python 3.11 reads .pth files in the ANSI code page).
    $site = Join-Path $venv 'Lib\site-packages'
    [IO.File]::WriteAllText((Join-Path $site 'tm.pth'), (Get-TmPth (Join-Path $root 'engine\src')), $utf8)
    $code = Run $venvPython @('-I', '-c', 'import tm, yaml, requests') 120
    if ($code -ne 0) { No "the venv of the '$Tier' tools cannot import the engine (exit code $code)" $null }

    $info = [ordered]@{ tier = $Tier; plugin_root = $root; python = $TmPythonVersion; requirements_sha256 = $reqSha }
    [IO.File]::WriteAllText($marker, ($info | ConvertTo-Json), $utf8)
    Remove-Item -Force -LiteralPath $log -ErrorAction SilentlyContinue
}

if ($Report) {
    try { Install-TmPython $Tier } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
    exit 0
}
Install-TmPython $Tier
