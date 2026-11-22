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
# The readings E and H of a command, as bootstrap/command-words.awk builds them (it says what they
# hold): E (here $EW) for the dot-name glob, H ($HW) for the key-search rule. Other tools: E is Q.
function NeutText($t) { $t -replace '[*?\[ ;|&()<>{}]', '_' }
function BareText($t) { ($t -replace '["''`]', '') -replace "`n", ' ; ' }
function ShellLine($t) { $t -match '(^|[ ;|&(/\\])(sh|bash|zsh|dash|ksh|mksh|fish|pwsh|powershell|cmd|source|eval|iex|\.)(\.exe)?([ ;|&)]|$)' }
function RunsCode($c) {
    ($c -match '(^|[ /\\])(sh|bash|zsh|dash|ksh|mksh|fish|pwsh|powershell|cmd)(\.exe)?( .*)? +(-[a-z]*c|-command|-c[a-z]*|/[ck]) *$') -or
    ($c -match '(^| )(eval|iex|invoke-expression)( .*)? *$') -or ($c -match '(^| )/[ck] *$')
}
function PsGlob($t) { $t.Replace('\', '/') -match '^([^ ]*/)?\.[a-z0-9_-]*[*?][a-z0-9_.*?/-]*$' }
# Where PowerShell never expands a quoted string as a path (command-words.awk's psnopath says which),
# from the last 300 characters before it.
function PsNoPath([string]$str, [int]$n) {
    $b = if ($n -gt 300) { 'x' + $str.Substring($n - 300, 300) } else { $str.Substring(0, $n) }
    ($b -match '(^|[^a-z0-9_-])-(patt(e(rn?)?)?|lit(e(r(a(l(p(a(th?)?)?)?)?)?)?)?|pspath|lp)(:| +)$') -or
    ($b -match '(^|[^a-z0-9_-])-[ic]?((not)?match|replace|split) *$') -or
    ($b -match '\[ *(system\.)?(text\.regularexpressions\.)?regex *\] *((:: *[a-z]+ *\( *(([^(),;|&{}\n]|\([^();|&{}\n]*\))*, *)?)?)$')
}
function CommandWords([string]$s, [string]$mode) {
    $NL = "`n"; $L = $s.Length; $e = New-Object Text.StringBuilder; $h = New-Object Text.StringBuilder
    $cur = ''; $pend = @(); $ls = 0; $ar = 0
    for ($i = 0; $i -lt $L; $i++) {
        $c = $s[$i]
        if ($c -eq "`n") {
            [void]$e.Append(' ; '); [void]$h.Append(' ; '); $cur = ''
            $p = $i + 1
            if ($mode -eq 'ps') { $ls = $p; continue }
            $line = $s.Substring($ls, $i - $ls)
            foreach ($hd in $pend) {  # the heredoc bodies, one after the other
                $body = New-Object Collections.Generic.List[string]; $q = $p
                while ($q -lt $L) {
                    $j = $s.IndexOf([char]10, $q); $end = if ($j -ge 0) { $j } else { $L }
                    $ln = $s.Substring($q, $end - $q); $t = $ln
                    if ($hd.Dash) { $t = $t -replace '^\t+', '' }
                    $t = $t -replace '[ \t]+$', ''
                    $q = $end + 1
                    if ($t -ceq $hd.Word) { break }
                    $body.Add($ln)
                }
                $b = $body -join $NL
                if ((ShellLine $line) -or (-not $hd.Quoted -and $b -match '\$\(|`')) {
                    [void]$e.Append((BareText $b) + ' ; '); [void]$h.Append(($b -replace $NL, ' ; ') + ' ; ')
                }
                $p = $q
            }
            $pend = @(); $i = $p - 1; $ls = $p
            continue
        }
        if ($mode -eq 'ps') {
            if ($c -eq '`') {  # PowerShell's escape: the next character as it is
                $x = if ($i + 1 -lt $L) { [string]$s[$i + 1] } else { '' }; $i++
                if ($x -ne $NL) { [void]$e.Append($x); $cur += $x }
                [void]$h.Append("$c$x"); continue
            }
            if ($c -eq '@' -and $i + 1 -lt $L -and ($s[$i + 1] -eq "'" -or $s[$i + 1] -eq '"')) {
                $qc = [string]$s[$i + 1]; $j = $s.IndexOf([char]10, $i + 2)
                if ($j -ge 0 -and $s.Substring($i + 2, $j - $i - 2) -match '^[ \t]*$') {  # a here-string
                    $k = $s.IndexOf("$NL$qc@", $j, [StringComparison]::Ordinal)
                    $body = if ($k -ge 0) { $s.Substring($j + 1, $k - $j - 1) } else { $s.Substring($j + 1) }
                    if ($qc -eq '"' -and $body -match '\$\(') { [void]$e.Append((BareText $body)); [void]$h.Append(($body -replace $NL, ' ; ')) }
                    $i = if ($k -ge 0) { $k + 2 } else { $L }
                    continue
                }
            }
            if ($c -eq "'" -or $c -eq '"') {
                $t = New-Object Text.StringBuilder; $j = $i + 1
                while ($j -lt $L) {
                    $x = $s[$j]
                    if ($x -eq $c -and $j + 1 -lt $L -and $s[$j + 1] -eq $c) { [void]$t.Append($x); $j += 2; continue }
                    if ($c -eq '"' -and $x -eq '`') { [void]$t.Append($s.Substring($j, [Math]::Min(2, $L - $j))); $j += 2; continue }
                    if ($x -eq $c) { break }
                    [void]$t.Append($x); $j++
                }
                $t = $t.ToString()
                if ((RunsCode $cur) -or ((PsGlob $t) -and -not (PsNoPath $s $i)) -or ($c -eq '"' -and $t -match '\$\(')) { [void]$e.Append((BareText $t)) } else { [void]$e.Append((NeutText $t)) }
                $w = $s.Substring($i, [Math]::Min($j, $L - 1) - $i + 1); [void]$h.Append($w); $cur += $w; $i = $j
                continue
            }
            # -Path:.e* gives -Path its value: in E the value is a word of its own.
            if ($c -eq ':' -and $cur -match '(^| )-[A-Za-z][A-Za-z0-9_]*$') { [void]$e.Append(' ') } else { [void]$e.Append($c) }
            [void]$h.Append($c); $cur += $c
            if ($c -match '[;|&(]') { $cur = '' }
            continue
        }
        # bash
        if ($c -eq '\') {
            $x = if ($i + 1 -lt $L) { [string]$s[$i + 1] } else { '' }; $i++
            if ($x -match '^[*?\[]$') { [void]$e.Append('_') } elseif ($x -ne $NL) { [void]$e.Append("/$x") }
            [void]$h.Append("$c$x"); $cur += "$c$x"; continue
        }
        if ($c -eq "'" -or ($c -eq '$' -and $i + 1 -lt $L -and $s[$i + 1] -eq "'")) {
            $ansi = $c -eq '$'; if ($ansi) { $i++ }
            $t = New-Object Text.StringBuilder; $j = $i + 1
            while ($j -lt $L) {
                $x = $s[$j]
                if ($ansi -and $x -eq '\') { [void]$t.Append($s.Substring($j, [Math]::Min(2, $L - $j))); $j += 2; continue }
                if ($x -eq "'") { break }
                [void]$t.Append($x); $j++
            }
            $t = $t.ToString()
            if (RunsCode $cur) { [void]$e.Append((BareText $t)) } else { [void]$e.Append((NeutText $t)) }
            $w = $s.Substring($i, [Math]::Min($j, $L - 1) - $i + 1); if ($ansi) { $w = "`$$w" }
            [void]$h.Append($w); $cur += $w; $i = $j
            continue
        }
        if ($c -eq '"') {
            $t = New-Object Text.StringBuilder; $j = $i + 1
            while ($j -lt $L) {
                $x = $s[$j]
                if ($x -eq '\') { [void]$t.Append($s.Substring($j, [Math]::Min(2, $L - $j))); $j += 2; continue }
                if ($x -eq '"') { break }
                [void]$t.Append($x); $j++
            }
            $t = $t.ToString()
            if ((RunsCode $cur) -or $t -match '\$\(|`') { [void]$e.Append((BareText $t)) } else { [void]$e.Append((NeutText $t)) }
            $w = $s.Substring($i, [Math]::Min($j, $L - 1) - $i + 1); [void]$h.Append($w); $cur += $w; $i = $j
            continue
        }
        if ($c -eq '`') { [void]$e.Append(' '); [void]$h.Append($c); $cur = ''; continue }
        if ($c -eq '(' -and $i + 1 -lt $L -and $s[$i + 1] -eq '(') { $ar++ }
        if ($c -eq ')' -and $i + 1 -lt $L -and $s[$i + 1] -eq ')' -and $ar -gt 0) { $ar-- }
        if ($c -eq '<' -and $i + 1 -lt $L -and $s[$i + 1] -eq '<' -and -not ($i + 2 -lt $L -and $s[$i + 2] -eq '<') -and -not $ar) {
            $j = $i + 2; $dash = $false
            if ($j -lt $L -and $s[$j] -eq '-') { $dash = $true; $j++ }
            while ($j -lt $L -and ($s[$j] -eq ' ' -or $s[$j] -eq "`t")) { $j++ }
            $w = ''
            while ($j -lt $L -and $s[$j] -notmatch '[ \t;|&()<>\n]') { $w += $s[$j]; $j++ }
            if ($w) {
                $pend += [pscustomobject]@{ Dash = $dash; Quoted = ($w -match '["''\\]'); Word = ($w -replace '["''\\]', '') }
                $part = $s.Substring($i, $j - $i); [void]$e.Append($part); [void]$h.Append($part); $cur += $part; $i = $j - 1
                continue
            }
        }
        [void]$e.Append($c); [void]$h.Append($c); $cur += $c
        if ($c -match '[;|&(]') { $cur = '' }
    }
    return @((($e.ToString().Replace('\', '/')) -replace "`n", ' ; '), ($h.ToString() -replace "`n", ' ; '))
}
# (EW and HW: PowerShell names are case-blind, and $h is taken.)
$EW = $Q; $HW = $targets
if ($tool -match '^(Bash|PowerShell)$' -and $in.PSObject.Properties['command']) {
    try {
        $two = CommandWords (([string]$in.command) -replace '[\r\t\f\x08]', ' ') $(if ($tool -eq 'PowerShell') { 'ps' } else { 'bash' })
        $EW = $two[0]; $HW = $two[1]
    } catch { $EW = $Q; $HW = $targets }
}
$HP = $HW.Replace('\', '/')
$HQ = $HP -replace '["''`]', ''
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
    # The programs in guard-programs.txt, as one regex, the same as guard-secrets.sh builds. Run as a
    # script block, this file has no $PSScriptRoot: the plugin root comes from CLAUDE_PLUGIN_ROOT.
    $progs = @()
    $plugin = if ($env:CLAUDE_PLUGIN_ROOT) { $env:CLAUDE_PLUGIN_ROOT } elseif ($PSScriptRoot) { Split-Path $PSScriptRoot } else { '' }
    $list = @()
    if ($plugin) { try { $list = [IO.File]::ReadAllLines((Join-Path (Join-Path $plugin 'bootstrap') 'guard-programs.txt')) } catch { $list = @() } }
    foreach ($line in $list) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith('#') -or $line.StartsWith('outside:')) { continue }
        $one = ''
        foreach ($ch in $line.ToLowerInvariant().ToCharArray()) {
            if ($ch -eq '*') { $one += '[a-z0-9_*+-][a-z0-9_.*+-]*' }
            elseif ($ch -cmatch '[a-z0-9_/-]') { $one += $ch }
            else { $one += "[$ch]" }
        }
        $progs += $one
    }
    $prog = if ($progs.Count) { '^/(' + ($progs -join '|') + ')([ ;|&)<>]|$)' } else { '' }
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
            $pm = if ($prog) { [regex]::Match($rest, $prog) } else { $null }
            if ($pm -and $pm.Success) {
                $cut = $m.Index + $m.Length + 1 + $pm.Groups[1].Length
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
        Deny 'data-folder' "this call names the plugin's data folder, where secrets.env (the keys) is kept, other than as the full path of a program the plugin installed there" 'Use the tm command the playbook gives (tm tool ffmpeg, for example). Only the programs in the plugin''s bootstrap/guard-programs.txt (pixi, the environments'' python, ffmpeg, ffprobe, node, npm and npx) can be named, by their full path with nothing after it, for example "$TM_PLUGIN_DATA/envs/<folder>/envs/base/bin/ffmpeg".'
    } elseif ($any) {
        $joined = $stripped -join "`n"
        $re = '@[^ ;|&)]*[/{,]\.\.([/ ;|&),}]|$)|(cd|pushd|chdir|set-location|push-location|sl) +@|dirname|split-path|\.parent|-parent|pardir|realpath|readlink|\$\{[a-z_][a-z0-9_]*%'
        if (MatchCi $joined '[a-z_][a-z0-9_:]* *= *@|(^|[^a-z0-9_-])(ln|mklink|new-item)( |$)|symboliclink|junction') {
            $re += '|(^|[/ {,])\.\.([/ ;|&),}]|$)|(^|[^a-z0-9_-])(cd|pushd|chdir|set-location|push-location|sl)( |$)'
        }
        $hit = MatchCi $joined $re
        if ($hit) { Deny 'data-climb' "this call names a program in the plugin's data folder and climbs out of it, or moves into the folder" 'Run the program by its full path, without cd, .. or a parent-folder lookup.' }
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
            if ($hit) { Deny 'data-parent' "this call reads all of a folder that holds the plugin's data folder (/, home, ~/.claude or ~/.claude/plugins), where secrets.env (the keys) is kept" 'Search or copy a narrower folder, one outside ~/.claude/plugins/data (for the plugin''s own code, its folder: $TM_PLUGIN_ROOT). When the match is only text in the command (a / or ~ in a pattern), use the Grep tool with that folder as its path, or put the pattern in a file (grep -f).' }
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
        $hit = MatchCi $Q '(^|[/ =(])[^/ =(]*\.env([ ;|&)]|$)|(^|[/ =(])\.env\.[a-z0-9_-]+|api_keys'
    }
    # A dot-name glob only as a whole word the shell expands (guard-secrets.sh says why).
    $psre = ''
    if (-not $hit -and $workspace) {
        $hit = MatchCi $EW '(^|[ ;|&(<>{])([^ ;|&(<>{]*/)?\.[^/ .;|&()<>]*[*?]'
        if ($hit -and $tool -eq 'PowerShell') { $psre = " In PowerShell a quoted regex passes only after -Pattern, -match or -replace (Select-String -Pattern '.*' -Path notes.md)." }
    }
    if ($hit) { Deny 'key-store' "this call names a key store (.secrets/, api_keys.env or a workspace's .env file)" "Don't open, search or copy it: tm reads the keys itself. When it is only text in a note (a heredoc that names .secrets/ or .env), write that text to a file with the Write tool and use the file (a note appended from it).$psre" }
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
            # A full path is narrow when it is a folder or file outside the session's folder, and
            # covers it when it is that folder or one above it (guard-secrets.sh says more).
            $home0 = if ($HOME) { $HOME } elseif ($env:USERPROFILE) { $env:USERPROFILE } else { '' }
            $home0 = $home0.Replace('\', '/')
            $drive = $cl -match '^[a-z]:/'
            function NormPath($t) {
                if ($drive -and $t -match '^/[a-z](/|$)') { $t = $t.Substring(1, 1) + ':' + $t.Substring(2) }
                if ($t -ne '/') { $t = $t -replace '/+$', '' }
                $t
            }
            $cwdn = NormPath $cl; $wide = $false; $nar = $false
            foreach ($line in ($HQ -split "`n")) {
                $o = $line -replace '[0-9&]*[<>]+ *[^ ;|&()<>]*', ' '
                foreach ($t in ($o -split '[ ;|&()=]+')) {
                    if (-not $t) { continue }
                    $m = [regex]::Match($t, '^(~|\$home|\$\{home\}|%userprofile%|\$env:userprofile|\$userprofile|\$env:home)', 'IgnoreCase')
                    if ($home0 -and $m.Success) { $x = $t.Substring($m.Length); if (-not $x -or $x.StartsWith('/')) { $t = $home0 + $x } }
                    $l = NormPath $t.ToLowerInvariant()
                    if ($l -notmatch '^(/|[a-z]:(/|$))') { continue }
                    if ($l -eq '/' -or $l -eq $cwdn -or ("$cwdn/").StartsWith("$l/", [StringComparison]::Ordinal)) { $wide = $true }
                    else { try { if ((Test-Path -LiteralPath $t) -or (Test-Path -LiteralPath (NormPath $t))) { $nar = $true } } catch { } }
                }
            }
            if ((MatchCi $HP $rec) -and ((-not (MatchCi $HQ $narrow) -and -not $nar) -or (MatchCi $HQ $rootish) -or $wide)) { $hit = MatchCi $HP $words }
        }
    }
    if ($hit) { Deny 'key-search' "this search covers a folder that holds the workspace's key store (.secrets/ or a .env file) and looks for a key word" "Search a narrower path such as runs/ (the Grep tool's path, or a path in the command), or one file." }
}
if (-not $rule) { exit 0 }

$hit = ($hit -replace '[\x00-\x1f]', '') -replace '^[ ;&|({`"''=]*', '' -replace '[ ;&|)}>"'']*$', ''
$said = ''
if ($hit -and $rule -ne 'token') { $said = " It matched: $hit." }
$reason = "Blocked by the TrendsMesh playbooks plugin's key guard (rule: $rule): $what.$said $how Keys are never shown, not even masked: tm doctor says whether each key is set, and the user changes them in /plugin, under Installed, trendsmesh-playbooks, Configure options."
@{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny'; permissionDecisionReason = $reason } } | ConvertTo-Json -Compress -Depth 4
exit 0
