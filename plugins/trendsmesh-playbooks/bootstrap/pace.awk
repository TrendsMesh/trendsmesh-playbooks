# The pacer's decision for pace-mcp.sh (issue #129): the same rule as tm.trend_pace.decide, read its header.
# Input: the limits file (named by -v lim, or /dev/null), then the call log. Variables: now (ms), tool (the
# short name), margin and maxwait (ms), out (the new log, written here). Prints "go <seconds to wait>" or
# "deny <reason>"; on go the log gets the call's booked moment.
function hit(p, k) { return p == "*" || p == k }
function near(T, W, p,   i, n, d) {
  n = 0
  for (i = 1; i <= ne; i++) if (hit(p, ek[i])) { d = et[i] - T; if (d < 0) d = -d; if (d < W) n++ }
  return n
}
function used(b,   i, n) {
  n = 0
  for (i = 1; i <= ne; i++) if (hit(bp[b], ek[i]) && et[i] >= ba[b]) n++
  return n
}
function fits(T,   i) {
  for (i = 1; i <= nw; i++) if (hit(wp[i], tool) && near(T, ww[i] + margin, wp[i]) >= wl[i]) return 0
  for (i = 1; i <= nb; i++) if (hit(bp[i], tool) && T < bz[i] && used(i) >= br[i]) return 0
  return 1
}
BEGIN { FS = "\t"; nw = 0; nb = 0; ne = 0 }
FILENAME == lim {
  if ($1 == "window" && $2 + 0 > 0 && $3 + 0 > 0 && $4 != "") { nw++; ww[nw] = $2 + 0; wl[nw] = $3 + 0; wp[nw] = $4 }
  else if ($1 == "budget" && $5 != "") { nb++; br[nb] = $2 + 0; ba[nb] = $3 + 0; bz[nb] = $4 + 0; bp[nb] = $5; bt[nb] = $6 }
  next
}
match($0, /"t":[0-9]+/) {
  t = substr($0, RSTART + 4, RLENGTH - 4) + 0
  k = ""
  if (match($0, /"tool":"[A-Za-z0-9_-]*"/)) k = substr($0, RSTART + 8, RLENGTH - 9)
  ne++; et[ne] = t; ek[ne] = k
}
END {
  if (nw == 0) {
    nw = 3; ww[1] = 1000; wl[1] = 10; wp[1] = "*"
    ww[2] = 60000; wl[2] = 10; wp[2] = "search_trends"; ww[3] = 60000; wl[3] = 20; wp[3] = "get_trend_videos"
  }
  nc = 1; c[1] = now
  for (i = 1; i <= ne; i++) for (j = 1; j <= nw; j++)
    if (hit(wp[j], tool) && hit(wp[j], ek[i])) { x = et[i] + ww[j] + margin; if (x > now) c[++nc] = x }
  for (j = 1; j <= nb; j++) if (hit(bp[j], tool) && bz[j] + margin > now) c[++nc] = bz[j] + margin
  best = -1
  for (i = 1; i <= nc; i++)
    if (c[i] - now <= maxwait && (best < 0 || c[i] < best) && fits(c[i])) best = c[i]
  # keep what a later call can still need: the longest window, and the calls since a live budget's answer
  long = 0
  for (j = 1; j <= nw; j++) if (ww[j] > long) long = ww[j]
  since = now - long - margin
  for (j = 1; j <= nb; j++) if (bz[j] > now && ba[j] < since) since = ba[j]
  printf "" > out
  for (i = 1; i <= ne; i++) if (et[i] > since || et[i] >= now) printf "{\"t\":%.0f,\"tool\":\"%s\"}\n", et[i], ek[i] > out
  if (best >= 0) {
    printf "{\"t\":%.0f,\"tool\":\"%s\"}\n", best, tool > out
    close(out)
    printf "go %.3f\n", (best - now) / 1000
    exit
  }
  close(out)
  for (j = 1; j <= nb; j++) if (hit(bp[j], tool) && now < bz[j] && used(j) >= br[j]) {
    left = br[j] - used(j); if (left < 0) left = 0
    printf "deny TrendsMesh allows %d more calls until %s (from the latest get_usage answer), so this call was not made. Tell the user how many calls the pull still needs, stop and wait for the reset, then continue from the same place and fetch only what is not saved yet.\n", left, bt[j]
    exit
  }
  rate = "its rate"
  for (j = nw; j >= 1; j--) if (hit(wp[j], tool)) {
    rate = sprintf("%d %scalls per %g s", wl[j], wp[j] == "*" ? "" : tool " ", ww[j] / 1000)
    if (wp[j] != "*") break
  }
  printf "deny This TrendsMesh call would have to wait more than %d s: TrendsMesh allows %s, and this workspace has more calls than that queued already, so it was not made. Make it again in about a minute, with at most 10 TrendsMesh calls at once; the run continues from the same place.\n", maxwait / 1000, rate
}
