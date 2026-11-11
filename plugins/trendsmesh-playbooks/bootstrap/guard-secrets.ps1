# PreToolUse hook for Windows without Git Bash: the same check as guard-secrets.sh, rule for rule
# and in the same order (read its header for the rules). Fails open: anything it cannot read is
# allowed; prints nothing then. Regexes are written to mean the same in .NET and in POSIX ERE, and
# are tried line by line, as grep does.
try {
    # Claude Code sends UTF-8. Read the bytes as such: [Console]::In decodes with the console's
    # code page, which garbles a user folder with a Polish letter.
    $stdin = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), (New-Object System.Text.UTF8Encoding $false))
    $call = $stdin.ReadToEnd() | ConvertFrom-Json
} catch { exit 0 }
if (-not $call -or -not $call.tool_input) { exit 0 }
$in = $call.tool_input
# A field's value as the sh guard reads it: a line break as " ; ", other control spaces as spaces.
function Field($name) {
    if ($in.PSObject.Properties[$name]) { [string]$in.$name -replace '\n', ' ; ' -replace '[\r\t\f\x08]', ' ' } else { '' }
}
function Lines($list) { (@($list | Where-Object { $_ -ne '' }) -join "`n") }
# The first match of $re in $text, line by line: case-blind (MatchCi) or exact (MatchCs; not Mi,
# which is the Move-Item alias).
function Hit($text, $re, $opts) {
    foreach ($line in ([string]$text -split "`n")) {
        $m = [regex]::Match($line, $re, $opts)
        if ($m.Success) { return $m.Value }
    }
    return ''
}
function MatchCi($text, $re) { Hit $text $re ([Text.RegularExpressions.RegexOptions]::IgnoreCase) }
function MatchCs($text, $re) { Hit $text $re ([Text.RegularExpressions.RegexOptions]::None) }

$tool = [string]$call.tool_name
$gp = $null
switch -Regex ($tool) {
    '^Read$' { $targets = @(Field 'file_path') }
    '^Grep$' { $targets = @((Field 'path'), (Field 'pattern'), (Field 'glob')); $gp = @((Field 'path'), (Field 'glob')) }
    '^Glob$' { $targets = @((Field 'path'), (Field 'pattern')) }
    '^(Bash|PowerShell)$' { $targets = @(Field 'command') }
    '^(Edit|MultiEdit|Write|NotebookEdit)$' { $targets = @((Field 'file_path'), (Field 'notebook_path')) }
    default { exit 0 }
}
if ($null -eq $gp) { $gp = $targets }
$targets = Lines $targets
$gp = Lines $gp
$all = ($in | ConvertTo-Json -Compress -Depth 10)
# The three readings guard-secrets.sh names P, Q and N, for the paths and for the whole call.
$P = $gp.Replace('\', '/')
$Q = $P -replace '["''`]', ''
$N = $gp -replace '[\\"''`]', ''
$TN = $targets -replace '[\\"''`]', ''
$TP = $targets.Replace('\', '/')
$data = ([string]$env:CLAUDE_PLUGIN_DATA).Replace('\', '/')
$cwd = ([string]$call.cwd).Replace('\', '/')
$dl = $data.ToLowerInvariant(); $cl = $cwd.ToLowerInvariant()
$above = [bool]($dl -and $cl -and $dl.StartsWith("$cl/", [StringComparison]::Ordinal))

$workspace = [bool]($cl -match '/runs/0[0-9]-|/runs$')
if ($cwd) {
    if (Test-Path -LiteralPath (Join-Path $cwd '.secrets') -PathType Container) { $workspace = $true }
    if (Get-ChildItem -LiteralPath (Join-Path $cwd 'runs') -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^0[0-9]-' }) { $workspace = $true }
}

$rule = ''; $what = ''; $how = ''; $hit = ''
function Deny($r, $w, $h) {  # sets them in the caller's scope (the guard's own)
    Set-Variable -Name rule -Value $r -Scope 1; Set-Variable -Name what -Value $w -Scope 1; Set-Variable -Name how -Value $h -Scope 1
}

# Command position (guard-secrets.sh says where).
$AT = '(^|[;&|({`]|(^| )-[A-Za-z]*c +["'']?|(^| )/[cCkK] +|(^|[^A-Za-z0-9_-])(sudo|xargs|exec|command|nohup|time|env|then|do|else|elif|if|while|until|nice|stdbuf|!|timeout +[^ ]+) ) *'
$END = ' *([;|&)}>"'']|$)'

# token
if (MatchCs $all 'r8_[A-Za-z0-9]{30,}') {
    Deny 'token' 'this call holds a Replicate key (a token that starts with r8_)' 'Never write, pass or print a key: tm reads the keys itself.'
}
# data-cwd
if (-not $rule -and $dl -and $cl) {
    if (("$cl/").StartsWith("$dl/", [StringComparison]::Ordinal)) {
        $w = "this session's folder is inside the plugin's data folder, where secrets.env (the keys) is kept"
        $h = 'First cd back to the project folder; a plain cd is allowed.'
        if ($tool -match '^(Bash|PowerShell)$') {
            if (-not (MatchCi $targets '^ *cd( +[^;&|]*)? *$') -or (MatchCi $Q '(^|[/ ])\.\.([/ ]|$)')) { Deny 'data-cwd' $w $h }
        } elseif ($tool -match '^(Grep|Glob)$') { Deny 'data-cwd' $w $h }
    }
}
# secrets-file
if (-not $rule) {
    $hit = MatchCi "$P`n$N" 'secrets\.(env|e[*?[]|[*?[])|secrets(\*|\[|\?[^ ;|&)])|ecrets\.env|secret~[0-9]'
    if ($hit) { Deny 'secrets-file' 'this call names secrets.env, the file that holds the keys' "Don't open, search or copy it: tm reads it itself." }
}
# key-variable
if (-not $rule -and ($tool -ne 'Grep' -or $workspace)) {
    $hit = MatchCs $TN 'REPLICATE_API_TOKEN|ELEVENLABS_API_KEY'
    if (-not $hit) { $hit = MatchCi $TN '(env:|%|\$\{?)[A-Za-z_]*(replicate_api_token|elevenlabs_api_key)' }
    if ($hit) { Deny 'key-variable' 'this call names a key variable (Replicate or ElevenLabs)' "Don't print or test it: tm reads the keys itself." }
}
# env-dump
if (-not $rule -and $tool -match '^(Bash|PowerShell)$') {
    $re = "$AT([^ ;|&(]*/)?(env|printenv)( +-[A-Za-z0-9-]*)*$END|${AT}set$END|$AT(export|declare|typeset)( +-[pxg]+)*$END"
    $re += "|${AT}compgen +-[ve]|${AT}ps +[a-z]*e[a-z]*( |$)|/[ck] +set +[a-z0-9_]+$END"
    $re += '|\$\{![A-Za-z_][A-Za-z0-9_]*[*@]\}|/proc/[^/ ]*/environ|GetEnvironmentVariables'
    $re += '|(python[0-9.]*|node|perl|ruby|deno|bun|php) [^|&]*(os\.environ($|[^.[a-z_]|\.(items|copy|keys|values))|process\.env($|[^.[a-z_])|%env)'
    $re += '|(^|[^$A-Za-z0-9_:])env:/?( *([|)]|$)|\*|[A-Za-z0-9_]*[*?[])'
    $hit = MatchCi "$TP`n$TN" $re
    if ($hit) { Deny 'env-dump' 'this command prints the whole environment, which can hold the keys' 'Print only the variable you need, by name (for example echo "$TM_PLUGIN_ROOT").' }
}
# data-folder, data-climb and data-parent (guard-secrets.sh says how the mentions are read).
if (-not $rule) {
    $soh = [string][char]1
    $re = '(\$\{?(env:)?|%)?(claude|tm)_plugin_data[}%]?|plugins/data/[^/ ;|&)]*(trendsmesh|[*?[~])[^/ ;|&)]*'
    $re += '|plugins/data/?([ ;|&)]|$)|(^|[^a-z0-9_.-])data/trendsmesh-playbooks[^/ ;|&)]*|' + $soh
    $any = $false; $bad = $null; $parents = @(); $stripped = @()
    foreach ($s in ($Q -split "`n")) {
        foreach ($t in ($s.ToLowerInvariant() -split '[ ;|&()]+')) {
            if ($t -ne '/') { $t = $t -replace '/+$', '' }
            if (-not $t) { continue }
            if ($t -eq '/' -or $t -match '^(~|\$home|\$\{home\}|%userprofile%|\$env:userprofile)$' -or $t -match '(^|/)\.claude(/plugins)?$' `
                -or ($dl -and $t -match '^(/|[a-z]:/)' -and $dl.StartsWith("$t/", [StringComparison]::Ordinal)) `
                -or ($dl -and $cl -and ($t -eq '.' -or $t -eq '*' -or $t -eq './*') -and $dl.StartsWith("$cl/", [StringComparison]::Ordinal))) {
                $parents += $t
            }
        }
        $l = $s.ToLowerInvariant()
        if ($dl) {
            while (($i = $l.IndexOf($dl, [StringComparison]::Ordinal)) -ge 0) {
                $l = $l.Substring(0, $i) + $soh + $l.Substring($i + $dl.Length)
                $s = $s.Substring(0, $i) + $soh + $s.Substring($i + $dl.Length)
            }
        }
        while (($m = [regex]::Match($l, $re)).Success) {
            $any = $true
            $ref = $s.Substring($m.Index, $m.Length); $rest = $l.Substring($m.Index + $m.Length)
            if ($rest -cmatch '^/(envs|pixi)([/ ;|&)]|$)') {
                $cut = $m.Index + $m.Length + 5
                $l = $l.Substring(0, $m.Index) + '@' + $l.Substring($cut)
                $s = $s.Substring(0, $m.Index) + '@' + $s.Substring($cut)
                continue
            }
            if ($ref.Contains($soh)) { $ref = "the data folder's path" }
            $bad = $ref -replace '^[^$%a-zA-Z0-9.]', ''
            break
        }
        if ($null -ne $bad) { break }
        $stripped += $l
    }
    if ($null -ne $bad) {
        $hit = $bad
        Deny 'data-folder' "this call names the plugin's data folder, where secrets.env (the keys) is kept, outside its envs/ and pixi/ folders" 'To run a tool the plugin installed, name it by its full path under envs/ or pixi/ (for example "$TM_PLUGIN_DATA/envs/.../bin/ffmpeg"), or use tm tool ffmpeg.'
    } elseif ($any) {
        $joined = $stripped -join "`n"
        $re = '@[^ ;|&)]*[/{,]\.\.([/ ;|&),}]|$)|(cd|pushd|chdir|set-location|push-location|sl) +@|dirname|split-path|\.parent|-parent|pardir|realpath|readlink|\$\{[a-z_][a-z0-9_]*%'
        if (MatchCi $joined '[a-z_][a-z0-9_:]* *= *@|(^|[^a-z0-9_-])(ln|mklink|new-item)( |$)|symboliclink|junction') {
            $re += '|(^|[/ {,])\.\.([/ ;|&),}]|$)|(^|[^a-z0-9_-])(cd|pushd|chdir|set-location|push-location|sl)( |$)'
        }
        $hit = MatchCi $joined $re
        if ($hit) { Deny 'data-climb' "this call names the plugin's data folder and climbs out of its envs/ or pixi/ folder, or moves into it" 'Run the tool by its full path, without cd, .. or a parent-folder lookup.' }
    }
    if (-not $rule) {
        $hit = if ($parents.Count) { $parents[0] } else { '' }
        if (-not $hit -and $tool -eq 'Grep' -and $above -and -not (Field 'path')) { $hit = "the session's folder" }
        if ($hit) {
            if ($tool -match '^(Bash|PowerShell)$') {
                $rec = "$AT(rg|ag|ack|find|tar|zip|rsync|7z)( |$)|(grep|egrep|fgrep)( [^|;&]*)? -[a-z]*r|(grep|egrep|fgrep) [^|;&]*--recursive"
                $rec += '|(^|[^a-z0-9_-])cp( [^|;&]*)? -[a-z]*[ra]|-recurse|robocopy|xcopy|compress-archive|findstr [^|;&]*/s'
                if (-not (MatchCi $TP $rec)) { $hit = '' }
            } elseif ($tool -ne 'Grep') { $hit = '' }
            if ($hit) { Deny 'data-parent' "this call reads all of a folder that holds the plugin's data folder (/, home, ~/.claude or ~/.claude/plugins), where secrets.env (the keys) is kept" 'Search or copy a narrower folder, one outside ~/.claude/plugins/data.' }
        }
    }
}
# plugins-glob
if (-not $rule) {
    $hit = MatchCi $Q '\.claude/([^/ ]*[*?[][^/ ]*/|plugins/[^/ ]*[*?[])'
    if ($hit) { Deny 'plugins-glob' "this call uses a wildcard inside .claude, which can reach the plugin's data folder where the keys are kept" 'Name the folder exactly, without * or ?.' }
}
# key-store and key-search
function StoreAt($dir) {  # does folder $dir hold .secrets/ or a .env file?
    if (Test-Path -LiteralPath (Join-Path $dir '.secrets')) { return $true }
    if (Test-Path -LiteralPath (Join-Path $dir '.env')) { return $true }
    return [bool](Get-ChildItem -LiteralPath $dir -Filter '*.env' -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '?*.env' -and $_.Name -notlike '.*' } | Select-Object -First 1)
}
if (-not $rule -and $tool -ne 'Glob') {
    $hit = MatchCi $Q '(^|[/ =(])\.secrets(/|[ ;|&)]|$)|api_keys\.env'
    if (-not $hit -and $workspace) {
        $hit = MatchCi $Q '(^|[/ =(])[^/ =(]*\.env([ ;|&)]|$)|(^|[/ =(])\.env\.[a-z0-9_-]+|(^|[/ =(])\.[^/ .]*[*?]|api_keys'
    }
    if ($hit) { Deny 'key-store' "this call names a key store (.secrets/, api_keys.env or a workspace's .env file)" "Don't open, search or copy it: tm reads the keys itself." }
}
if (-not $rule -and ($workspace -or $tool -eq 'Grep')) {
    $hit = ''
    $words = 'replicate|elevenlabs|token|secret|api|key|r8_|sk_|(^| )(''''|"")( |$)'
    if ($tool -eq 'Grep') {
        $root = (Field 'path').Replace('\', '/')
        if (-not $root) { $root = $cwd } elseif ($root -notmatch '^(/|[A-Za-z]:/)') { $root = "$cwd/$root" }
        if ((Test-Path -LiteralPath (Join-Path $root '.secrets')) -or ($workspace -and (StoreAt $root))) {
            $pat = Field 'pattern'
            $hit = MatchCi $pat $words
            if (-not $hit -and (MatchCi $pat '^[.^$*+?()|= -]*$')) { $hit = $pat }
        }
    } elseif ($tool -match '^(Bash|PowerShell)$') {
        if ($workspace -and $cwd -and ((StoreAt $cwd) -or (StoreAt "$cwd/.."))) {
            $rec = "$AT(rg|ag|ack|find)( |$)|$AT(grep|egrep|fgrep)( [^|;&]*)? -[a-z]*r|$AT(grep|egrep|fgrep) [^|;&]*--recursive"
            $rec += '|findstr [^|;&]*/s|(get-childitem|gci|dir|ls) [^|;&]*-r[^|;&]*\| *(select-string|sls)'
            $narrow = '(rg|ag|ack|find|grep|egrep|fgrep|findstr|select-string|sls|get-childitem|gci|dir|ls)( [^|;&>]*)? [a-z0-9_][^ |;&)>]*/'
            $rootish = '(^| )(\.|\./|\.\.|\.\./|\*|\.\*|\./\*|\*/)( |[;|&)]|$)'
            if ((MatchCi $TP $rec) -and (-not (MatchCi $Q $narrow) -or (MatchCi $Q $rootish))) { $hit = MatchCi $TP $words }
        }
    }
    if ($hit) { Deny 'key-search' "this search covers a folder that holds the workspace's key store (.secrets/ or a .env file) and looks for a key word" "Search a narrower path such as runs/ (the Grep tool's path, or a path in the command), or one file." }
}
if (-not $rule) { exit 0 }

$hit = ($hit -replace '[\x00-\x1f]', '') -replace '^[ ;&|({`"''=]*', '' -replace '[ ;&|)}>"'']*$', ''
$said = ''
if ($hit -and $rule -ne 'token') { $said = " It matched: $hit." }
$reason = "Blocked by the TrendsMesh playbooks plugin's key guard (rule: $rule): $what.$said $how Keys are never shown, not even masked: tm doctor says whether each key is set, and the user changes them in /plugin, trendsmesh-playbooks, configure."
@{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny'; permissionDecisionReason = $reason } } | ConvertTo-Json -Compress -Depth 4
exit 0
