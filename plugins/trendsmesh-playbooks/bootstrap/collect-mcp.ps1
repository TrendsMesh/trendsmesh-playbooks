# PostToolUse hook for Windows without Git Bash: the same as collect-mcp.sh (read its header). Run
# as a script block, so it reads the hook's own stdin; $PSScriptRoot is empty there, so the plugin
# root comes from CLAUDE_PLUGIN_ROOT. Prints only what `tm trends spool` prints, or one fixed line
# when tm itself fails; always exits 0.
function Value($text, $key) {
    # The first string value of $key. Only that one key is decoded: decoding the whole event (an
    # answer can be large) is slow, and 5.1's ConvertFrom-Json refuses texts over 2 MB. A key inside
    # the answer's text is escaped (\"cwd\"), so it does not match.
    $m = [regex]::Match($text, '"' + $key + '"\s*:\s*"(?:[^"\\]|\\.)*"')
    if (-not $m.Success) { return '' }
    return [string](('{' + $m.Value + '}') | ConvertFrom-Json).$key
}
try {
    # Claude Code sends UTF-8: read the bytes as such, not in the console's code page.
    $stdin = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), (New-Object System.Text.UTF8Encoding $false))
    $text = $stdin.ReadToEnd()
    $dir = Value $text 'cwd'
    $session = Value $text 'session_id'
} catch { exit 0 }
# Only this session's own marker (one per Claude Code session); a session id that is not a plain file
# name never names one (tm's own rule, trend_spool.safe_session).
if ($session -cnotmatch '^[A-Za-z0-9_-]{1,128}$') { exit 0 }
$name = '.trendsmesh\collect\' + $session + '.json'
$found = $false
while ($dir) {
    if (Test-Path -LiteralPath (Join-Path $dir $name) -PathType Leaf) { $found = $true; break }
    $up = Split-Path -Parent $dir
    if ($up -eq $dir) { break }
    $dir = $up
}
if (-not $found -or -not $env:CLAUDE_PLUGIN_ROOT) { exit 0 }
try { $marker = [IO.File]::ReadAllText((Join-Path $dir $name)) | ConvertFrom-Json } catch { $marker = $null }

$env:TM_PLUGIN_ROOT = $env:CLAUDE_PLUGIN_ROOT
if ($env:CLAUDE_PLUGIN_DATA) { $env:TM_PLUGIN_DATA = $env:CLAUDE_PLUGIN_DATA }
# The event goes through a UTF-8 file: a pipe to a native command would be re-encoded on 5.1.
$file = Join-Path ([IO.Path]::GetTempPath()) ('tm-event-' + [guid]::NewGuid().ToString('N') + '.json')
$rc = 1
try {
    [IO.File]::WriteAllText($file, $text, (New-Object System.Text.UTF8Encoding $false))
    $out = & (Join-Path $env:CLAUDE_PLUGIN_ROOT 'bin\tm.cmd') trends spool --event $file 2>$null
    $rc = $LASTEXITCODE
} catch {
} finally {
    Remove-Item -LiteralPath $file -Force -ErrorAction SilentlyContinue
}
if ($rc -eq 0) {
    if ($out) { $out -join "`n" }
    exit 0
}
# tm itself failed (spool always exits 0, so the engine never ran): say so, and log it in the run.
try {
    $research = Join-Path (Join-Path $dir ([string]$marker.run)) '02_research'
    if ($marker.run -and (Test-Path -LiteralPath $research -PathType Container)) {
        $tool = (Value $text 'tool_name') -replace '^.*__', ''
        $line = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') + "`t$tool`tthe engine did not start (tm exited $rc)`n"
        [IO.File]::AppendAllText((Join-Path $research 'collect_failures.log'), $line, (New-Object System.Text.UTF8Encoding $false))
    }
} catch {}
'{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "This answer was not saved to the run (the plugin''s engine did not start). Save it with tm trends ingest --run <run folder> --tool <tool name> --input <file with the tool''s input> --file <file with this answer>; tm doctor says why the engine did not start. The run continues from the same place."}}'
exit 0
