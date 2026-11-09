# PreToolUse hook for Windows without Git Bash: the same check as guard-secrets.sh (read its
# header for the rules). Fails open: anything it cannot read is allowed; prints nothing then.
try {
    # Claude Code sends UTF-8. Read the bytes as such: [Console]::In decodes with the console's
    # code page, which garbles a user folder with a Polish letter.
    $stdin = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), (New-Object System.Text.UTF8Encoding $false))
    $call = $stdin.ReadToEnd() | ConvertFrom-Json
} catch { exit 0 }
if (-not $call -or -not $call.tool_input) { exit 0 }
$in = $call.tool_input
function Field($name) { if ($in.PSObject.Properties[$name]) { [string]$in.$name } else { '' } }
$tool = [string]$call.tool_name
switch -Regex ($tool) {
    '^Read$' { $targets = @(Field 'file_path') }
    '^Grep$' { $targets = @((Field 'path'), (Field 'pattern'), (Field 'glob')); $gpaths = @((Field 'path'), (Field 'glob')) }
    '^Glob$' { $targets = @((Field 'path'), (Field 'pattern')) }
    '^(Bash|PowerShell)$' { $targets = @(Field 'command') }
    '^(Edit|MultiEdit|Write|NotebookEdit)$' { $targets = @((Field 'file_path'), (Field 'notebook_path')) }
    default { exit 0 }
}
if ($tool -ne 'Grep') { $gpaths = $targets }
$t = ($targets -join "`n")
$p = $t.Replace('\', '/')
$g = ($gpaths -join "`n").Replace('\', '/')
$all = ($in | ConvertTo-Json -Compress -Depth 10)
$cwd = ([string]$call.cwd).Replace('\', '/')
$workspace = ($cwd -match '/runs/01-refresh-ad(/|$)') -or ($cwd -and (Test-Path -LiteralPath (Join-Path $cwd 'runs/01-refresh-ad')))

$deny = $false
$data = ([string]$env:CLAUDE_PLUGIN_DATA).Replace('\', '/')
if ($data -and $p.IndexOf($data, [StringComparison]::OrdinalIgnoreCase) -ge 0) { $deny = $true }
if ($p -cmatch 'CLAUDE_PLUGIN_DATA|TM_PLUGIN_DATA') { $deny = $true }
if ($p -match '\.claude/plugins/data/([^/ "]*trendsmesh|[^/ "]*[*?\[])') { $deny = $true }
if ($g -match 'secrets\.env') { $deny = $true }
$names = 'REPLICATE_API_TOKEN|ELEVENLABS_API_KEY'
if ($tool -eq 'Grep') { if ($workspace -and $t -cmatch $names) { $deny = $true } }
elseif ($t -cmatch $names) { $deny = $true }
if ($all -cmatch 'r8_[A-Za-z0-9]{30,}') { $deny = $true }
if ($workspace -and -not $deny) {
    $words = 'replicate|elevenlabs|token|secret|api[ _-]?key'
    # A reader counts only in command position (guard-secrets.sh says where), so "od", "more",
    # "less" or "type" inside an argument (an ad's line) is no reader.
    $at = '(^|[;&|(`]|-[A-Za-z]*c\s+["'']|(^|[^A-Za-z0-9_-])(sudo|xargs|exec|command|env|nohup|time)\s)\s*'
    $verbs = '(?m)' + $at + '(grep|egrep|fgrep|rg|ag|ack|awk|sed|cat|head|tail|less|more|strings|xxd|od|findstr|Select-String|Get-Content|gc|type)([^A-Za-z0-9_-]|$)'
    if ($tool -match '^(Read|Grep|Glob)$' -and $t -match $words) { $deny = $true }
    if ($tool -match '^(Bash|PowerShell)$' -and $t -match $verbs -and $t -match $words) { $deny = $true }
}
if (-not $deny) { exit 0 }
$reason = "Blocked by the TrendsMesh playbooks plugin: this call would read or search for a Replicate or ElevenLabs key, or look inside the plugin's data folder where they are kept. Keys are never shown, not even masked. To check a key, run tm doctor (it says whether each key is set); the user sees and changes it in /plugin, trendsmesh-playbooks, configure. If this call has nothing to do with keys, rephrase it so it does not name a key file, a key variable or that folder."
@{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny'; permissionDecisionReason = $reason } } | ConvertTo-Json -Compress -Depth 4
exit 0
