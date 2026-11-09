# Prints every string value of one JSON document as "<path><TAB><value>", one per line, with
# paths like tool_input.file_path or tool_input.edits.0.new_string. POSIX awk, linear time:
# escaped backslashes and quotes are swapped for placeholders, then the text splits on quotes,
# so odd pieces are structure and even pieces are strings. \n, \t and the like become spaces;
# \uXXXX escapes are kept as written. Numbers, booleans and null are skipped. Unbalanced quotes
# print nothing (the caller then allows the call: the guard fails open).
{ s = s $0 " " }   # JSON strings never hold a raw line break, so lines join with a space
END {
  gsub(/\\\\/, "\003", s)
  gsub(/\\"/, "\002", s)
  n = split(s, p, "\"")
  if (n % 2 == 0) exit 0
  d = 0
  for (i = 1; i <= n; i++) {
    if (i % 2 == 1) {
      seg = p[i]; L = length(seg)
      for (j = 1; j <= L; j++) {
        c = substr(seg, j, 1)
        if (c == "{") { d++; kind[d] = "o"; ek[d] = 1; key[d] = "" }
        else if (c == "[") { d++; kind[d] = "a"; idx[d] = 0 }
        else if (c == "}" || c == "]") { if (d > 0) d-- }
        else if (c == ",") { if (kind[d] == "o") ek[d] = 1; else idx[d]++ }
        else if (c == ":") { ek[d] = 0 }
      }
      continue
    }
    v = p[i]
    if (kind[d] == "o" && ek[d]) { key[d] = v; continue }
    path = ""
    for (k = 1; k <= d; k++) path = path (k > 1 ? "." : "") (kind[k] == "o" ? key[k] : idx[k])
    gsub(/\\[nrtbf]/, " ", v)
    gsub(/\\\//, "/", v)
    gsub(/\003/, "\\", v)
    gsub(/\002/, "\"", v)
    gsub(/\t/, " ", v)
    print path "\t" v
  }
}
