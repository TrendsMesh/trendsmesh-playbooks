# Reads one shell command (its line breaks as \004) and prints two readings of it for
# guard-secrets.sh (guard-secrets.ps1 builds the same two in PowerShell):
#   E<TAB>...  the words the shell would expand: every quoted string, heredoc body and PowerShell
#              here-string is taken out, so a regex or a note in them is no path glob. A quoted
#              string stays in as words (its quotes dropped) where a shell runs it as code: after
#              sh -c, bash -c, cmd /c, pwsh -Command, eval, iex, or a double-quoted string with $( or
#              a backtick. In PowerShell (mode=ps) a quoted string that is all one dot-name glob
#              ('.e*') stays in too, since PowerShell expands wildcards inside quotes, unless it
#              stands where it is a search expression or a literal path (psnopath). A heredoc
#              body stays in when a shell reads it (bash <<EOF, cat <<EOF | sh) or when its
#              delimiter is unquoted and the body holds $( or a backtick.
#   H<TAB>...  the command as written, without the heredoc bodies and here-strings taken out above.
# A line break becomes " ; " in both. POSIX awk; mode is bash (the default) or ps.
function neut(t) { gsub(/[*?[ ;|&()<>{}]/, "_", t); return t }   # quoted text: no glob, no word break
function bare(t) { gsub(/["'`]/, "", t); gsub(NL, " ; ", t); return t }   # text a shell runs
function shellline(t) {  # does this line hand its heredoc to a shell?
  t = tolower(t)
  return t ~ /(^|[ ;|&(\/\\])(sh|bash|zsh|dash|ksh|mksh|fish|pwsh|powershell|cmd|source|eval|iex|\.)(\.exe)?([ ;|&)]|$)/
}
function runs_code(c) {  # is the next quoted string, after the command text c, run as code?
  c = tolower(c)
  if (c ~ /(^|[ \/\\])(sh|bash|zsh|dash|ksh|mksh|fish|pwsh|powershell|cmd)(\.exe)?( .*)? +(-[a-z]*c|-command|-c[a-z]*|\/[ck]) *$/) return 1
  if (c ~ /(^| )(eval|iex|invoke-expression)( .*)? *$/) return 1
  return c ~ /(^| )\/[ck] *$/
}
function psglob(t) {  # PowerShell: is the whole quoted text one dot-name glob (.e*, dir\.s*\*)?
  t = tolower(t); gsub(/\\/, "/", t)
  return t ~ /^([^ ]*\/)?\.[a-z0-9_-]*[*?][a-z0-9_.*?\/-]*$/
}
# PowerShell: does a quoted string right after the text b stand where PowerShell never expands it
# as a path? Only the value of -Pattern (or of -Patt and longer: -Pat and -Pa could be -Path), of
# -LiteralPath (-Lit and longer, -PSPath, -LP), the right side of -match, -replace or -split (and
# their i, c and not forms), and a [regex] cast or the first two arguments of a [regex]:: method.
# Anything else (a positional argument, -Path, -Filter, a variable, a string piped on, something
# in parentheses) stays a path, so what this can't place is still denied. b is the n characters
# before the quote; only their last 300 are read (a longer [regex]:: call stays denied).
function psnopath(str, n,   b) {
  b = tolower(n > 300 ? "x" substr(str, n - 299, 300) : substr(str, 1, n))
  if (b ~ /(^|[^a-z0-9_-])-(patt(e(rn?)?)?|lit(e(r(a(l(p(a(th?)?)?)?)?)?)?)?|pspath|lp)(:| +)$/) return 1
  if (b ~ /(^|[^a-z0-9_-])-[ic]?((not)?match|replace|split) *$/) return 1
  return b ~ /\[ *(system\.)?(text\.regularexpressions\.)?regex *\] *((:: *[a-z]+ *\( *(([^(),;|&{}\004]|\([^();|&{}\004]*\))*, *)?)?)$/
}
BEGIN { NL = sprintf("%c", 4) }
{
  s = $0; L = length(s); e = ""; h = ""; cur = ""; np = 0; ls = 1; ar = 0
  for (i = 1; i <= L; i++) {
    c = substr(s, i, 1)
    if (c == NL) {
      e = e " ; "; h = h " ; "; cur = ""
      p = i + 1
      if (mode == "ps") {   # nothing pending: here-strings are read where they open
        ls = p; continue
      }
      line = substr(s, ls, i - ls)
      for (k = 1; k <= np; k++) {   # the heredoc bodies, one after the other
        body = ""; q = p; found = 0
        while (q <= L) {
          j = index(substr(s, q), NL); end = j ? q + j - 1 : L + 1
          ln = substr(s, q, end - q); t = ln
          if (hdash[k]) sub(/^\t+/, "", t)
          sub(/[ \t]+$/, "", t)
          q = end + 1
          if (t == hword[k]) { found = 1; break }
          body = body (body == "" ? "" : NL) ln
        }
        keep = shellline(line) || (!hquot[k] && body ~ /\$\(|`/)
        if (keep) { e = e bare(body) " ; "; b = body; gsub(NL, " ; ", b); h = h b " ; " }
        p = q
      }
      np = 0; i = p - 1; ls = p
      continue
    }
    if (mode == "ps") {
      if (c == "`") {   # PowerShell's escape: the next character as it is
        x = substr(s, i + 1, 1); i++
        if (x != NL) { e = e x; cur = cur x }
        h = h c x; continue
      }
      if (c == "@" && (substr(s, i + 1, 1) == "'" || substr(s, i + 1, 1) == "\"")) {
        qc = substr(s, i + 1, 1); rest = substr(s, i + 2); j = index(rest, NL)
        if (j && substr(rest, 1, j - 1) ~ /^[ \t]*$/) {   # a here-string: @' or @" alone on its line
          body = substr(rest, j + 1); k = index(body, NL qc "@")
          if (k) body = substr(body, 1, k - 1)
          if (qc == "\"" && body ~ /\$\(/) { e = e bare(body); b = body; gsub(NL, " ; ", b); h = h b }
          i = k ? i + 1 + j + k + 2 : L
          continue
        }
      }
      if (c == "'" || c == "\"") {
        t = ""; j = i + 1
        while (j <= L) {
          x = substr(s, j, 1)
          if (x == c && substr(s, j + 1, 1) == c) { t = t x; j += 2; continue }   # '' or ""
          if (c == "\"" && x == "`") { t = t substr(s, j, 2); j += 2; continue }
          if (x == c) break
          t = t x; j++
        }
        if (runs_code(cur) || (psglob(t) && !psnopath(s, i - 1)) || (c == "\"" && t ~ /\$\(/)) e = e bare(t)
        else e = e neut(t)
        h = h substr(s, i, j - i + 1); cur = cur substr(s, i, j - i + 1); i = j
        continue
      }
      # -Path:.e* gives -Path its value: in E the value is a word of its own.
      if (c == ":" && cur ~ /(^| )-[A-Za-z][A-Za-z0-9_]*$/) e = e " "
      else e = e c
      h = h c; cur = cur c
      if (c ~ /[;|&(]/) cur = ""
      continue
    }
    # bash
    if (c == "\\") {
      x = substr(s, i + 1, 1); i++
      if (x ~ /[*?[]/) e = e "_"
      else if (x != NL) e = e "/" x
      h = h c x; cur = cur c x; continue
    }
    if (c == "'" || (c == "$" && substr(s, i + 1, 1) == "'")) {
      ansi = c == "$"; if (ansi) i++
      t = ""; j = i + 1
      while (j <= L) {
        x = substr(s, j, 1)
        if (ansi && x == "\\") { t = t substr(s, j, 2); j += 2; continue }
        if (x == "'") break
        t = t x; j++
      }
      e = e (runs_code(cur) ? bare(t) : neut(t))
      h = h (ansi ? "$" : "") substr(s, i, j - i + 1); cur = cur substr(s, i, j - i + 1); i = j
      continue
    }
    if (c == "\"") {
      t = ""; j = i + 1
      while (j <= L) {
        x = substr(s, j, 1)
        if (x == "\\") { t = t substr(s, j, 2); j += 2; continue }
        if (x == "\"") break
        t = t x; j++
      }
      if (runs_code(cur) || t ~ /\$\(|`/) e = e bare(t)
      else e = e neut(t)
      h = h substr(s, i, j - i + 1); cur = cur substr(s, i, j - i + 1); i = j
      continue
    }
    if (c == "`") { e = e " "; h = h c; cur = ""; continue }   # command substitution: its words count
    if (c == "(" && substr(s, i + 1, 1) == "(") ar++   # $(( )): a << there is a shift
    if (c == ")" && substr(s, i + 1, 1) == ")" && ar > 0) ar--
    if (c == "<" && substr(s, i + 1, 1) == "<" && substr(s, i + 2, 1) != "<" && !ar) {
      j = i + 2; dash = 0
      if (substr(s, j, 1) == "-") { dash = 1; j++ }
      while (substr(s, j, 1) ~ /[ \t]/) j++
      w = ""
      while (j <= L && substr(s, j, 1) !~ /[ \t;|&()<>]/ && substr(s, j, 1) != NL) { w = w substr(s, j, 1); j++ }
      if (w != "") {
        np++; hdash[np] = dash; hquot[np] = w ~ /["'\\]/
        gsub(/["'\\]/, "", w); hword[np] = w
        e = e substr(s, i, j - i); h = h substr(s, i, j - i); cur = cur substr(s, i, j - i); i = j - 1
        continue
      }
    }
    e = e c; h = h c; cur = cur c
    if (c ~ /[;|&(]/) cur = ""
  }
  gsub(/\\/, "/", e); gsub(NL, " ; ", e); gsub(NL, " ; ", h)
  print "E\t" e
  print "H\t" h
}
