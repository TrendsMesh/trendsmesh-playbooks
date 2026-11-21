# PreToolUse hook for Windows without Git Bash: the pacer of pace-mcp.sh (read its header; the rule is
# tm.trend_pace's). Run as a script block, so it reads the hook's own stdin. The call log is the same
# <workspace>\.trendsmesh\pace.jsonl; the lock is pace.ps.lock beside it, held open with no sharing, so
# Windows releases it when the process ends (PowerShell has no atomic mkdir without a native call). Prints
# nothing (the call goes, after its wait) or one deny line; always exits 0, so a failure never blocks a call.
if ($env:EVAL_TM_PACE -eq 'off') { exit 0 }
function Value($text, $key) {
    # The first string value of $key (collect-mcp.ps1's): a key inside the input's text is escaped, so it does not match.
    $m = [regex]::Match($text, '"' + $key + '"\s*:\s*"(?:[^"\\]|\\.)*"')
    if (-not $m.Success) { return '' }
    return [string](('{' + $m.Value + '}') | ConvertFrom-Json).$key
}
function Hit($p, $k) { return ($p -eq '*') -or ($p -ceq $k) }
$margin = 300
$maxwait = 65000
$handle = $null
try {
    $stdin = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), (New-Object System.Text.UTF8Encoding $false))
    $text = $stdin.ReadToEnd()
    $tool = (Value $text 'tool_name') -replace '^.*__', ''
    if ($tool -cnotmatch '^[A-Za-z0-9_-]{1,64}$') { $tool = 'other' }
    $cwd = Value $text 'cwd'
    if (-not $cwd) { exit 0 }

    # The workspace: the cwd or the nearest folder above it with .trendsmesh\ or runs\0N-..., never the home folder.
    $homeDir = [Environment]::GetFolderPath('UserProfile').TrimEnd('\', '/')
    $ws = $null
    $d = $cwd.TrimEnd('\', '/')
    while ($d) {
        if ($homeDir -and ($d -ieq $homeDir)) { break }
        if (Test-Path -LiteralPath (Join-Path $d '.trendsmesh') -PathType Container) { $ws = $d; break }
        $runs = Join-Path $d 'runs'
        if ((Test-Path -LiteralPath $runs -PathType Container) -and
            (Get-ChildItem -LiteralPath $runs -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^0[0-9]-' })) {
            $ws = $d; break
        }
        $up = Split-Path -Parent $d
        if (-not $up -or $up -eq $d) { break }
        $d = $up
    }
    if (-not $ws) { $ws = $cwd }
    $at = Join-Path $ws '.trendsmesh'
    [IO.Directory]::CreateDirectory($at) | Out-Null

    $lockPath = Join-Path $at 'pace.ps.lock'
    $deadline = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() + 5000
    while (-not $handle) {
        try {
            $handle = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        } catch [System.IO.IOException] {
            if ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() -gt $deadline) { exit 0 }   # never block a call
            Start-Sleep -Milliseconds 20
        }
    }
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()

    $windows = @()
    $budgets = @()
    $limPath = Join-Path $at 'pace-limits.tsv'
    if (Test-Path -LiteralPath $limPath -PathType Leaf) {
        foreach ($line in [IO.File]::ReadAllLines($limPath)) {
            $f = $line -split "`t"
            if ($f[0] -eq 'window' -and $f.Count -ge 4 -and [long]$f[1] -gt 0 -and [long]$f[2] -gt 0) {
                $windows += , @([long]$f[1], [long]$f[2], $f[3])
            } elseif ($f[0] -eq 'budget' -and $f.Count -ge 6) {
                $budgets += , @([long]$f[1], [long]$f[2], [long]$f[3], $f[4], $f[5])
            }
        }
    }
    if ($windows.Count -eq 0) {
        $windows = @(@([long]1000, [long]10, '*'), @([long]60000, [long]10, 'search_trends'), @([long]60000, [long]20, 'get_trend_videos'))
    }
    $logPath = Join-Path $at 'pace.jsonl'
    $entries = @()
    if (Test-Path -LiteralPath $logPath -PathType Leaf) {
        foreach ($line in [IO.File]::ReadAllLines($logPath)) {
            $t = [regex]::Match($line, '"t":(\d+)')
            if (-not $t.Success) { continue }
            $k = [regex]::Match($line, '"tool":"([A-Za-z0-9_-]*)"')
            $entries += , @([long]$t.Groups[1].Value, $(if ($k.Success) { $k.Groups[1].Value } else { '' }))
        }
    }
    function Used($b) { return @($entries | Where-Object { (Hit $b[3] $_[1]) -and $_[0] -ge $b[1] }).Count }
    function Fits($T) {
        foreach ($w in $windows) {
            if (-not (Hit $w[2] $tool)) { continue }
            $n = @($entries | Where-Object { (Hit $w[2] $_[1]) -and [Math]::Abs($_[0] - $T) -lt ($w[0] + $margin) }).Count
            if ($n -ge $w[1]) { return $false }
        }
        foreach ($b in $budgets) {
            if ((Hit $b[3] $tool) -and $T -lt $b[2] -and (Used $b) -ge $b[0]) { return $false }
        }
        return $true
    }
    $moments = @($now)
    foreach ($e in $entries) {
        foreach ($w in $windows) {
            if ((Hit $w[2] $tool) -and (Hit $w[2] $e[1])) { $x = $e[0] + $w[0] + $margin; if ($x -gt $now) { $moments += $x } }
        }
    }
    foreach ($b in $budgets) { if ((Hit $b[3] $tool) -and ($b[2] + $margin) -gt $now) { $moments += $b[2] + $margin } }
    $best = $null
    foreach ($m in ($moments | Sort-Object -Unique)) {
        if ($m - $now -gt $maxwait) { break }
        if (Fits $m) { $best = $m; break }
    }

    # Keep what a later call can still need: the longest window, and the calls since a live budget's answer.
    $long = ($windows | ForEach-Object { $_[0] } | Measure-Object -Maximum).Maximum
    $since = $now - $long - $margin
    foreach ($b in $budgets) { if ($b[2] -gt $now -and $b[1] -lt $since) { $since = $b[1] } }
    $sb = New-Object System.Text.StringBuilder
    foreach ($e in $entries) {
        if ($e[0] -gt $since -or $e[0] -ge $now) { [void]$sb.Append('{"t":' + $e[0] + ',"tool":"' + $e[1] + "`"}`n") }
    }
    if ($null -ne $best) { [void]$sb.Append('{"t":' + $best + ',"tool":"' + $tool + "`"}`n") }
    [IO.File]::WriteAllText($logPath, $sb.ToString(), (New-Object System.Text.UTF8Encoding $false))
    $handle.Dispose()
    $handle = $null

    if ($null -ne $best) {
        if ($best -gt $now) { Start-Sleep -Milliseconds ([int]($best - $now)) }
        exit 0
    }
    $reason = $null
    foreach ($b in $budgets) {
        if ((Hit $b[3] $tool) -and $now -lt $b[2] -and (Used $b) -ge $b[0]) {
            $left = [Math]::Max($b[0] - (Used $b), 0)
            $reason = "TrendsMesh allows $left more calls until $($b[4]) (from the latest get_usage answer), so this call was not made. Tell the user how many calls the pull still needs, stop and wait for the reset, then continue from the same place and fetch only what is not saved yet."
            break
        }
    }
    if (-not $reason) {
        $rate = 'its rate'
        for ($j = $windows.Count - 1; $j -ge 0; $j--) {
            $w = $windows[$j]
            if (-not (Hit $w[2] $tool)) { continue }
            $who = $(if ($w[2] -eq '*') { '' } else { "$tool " })
            $rate = "$($w[1]) ${who}calls per $($w[0] / 1000) s"
            if ($w[2] -ne '*') { break }
        }
        $reason = "This TrendsMesh call would have to wait more than $($maxwait / 1000) s: TrendsMesh allows $rate, and this workspace has more calls than that queued already, so it was not made. Make it again in about a minute, with at most 10 TrendsMesh calls at once; the run continues from the same place."
    }
    @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny'; permissionDecisionReason = $reason } } |
        ConvertTo-Json -Compress
} catch {
} finally {
    if ($handle) { $handle.Dispose() }
}
exit 0
