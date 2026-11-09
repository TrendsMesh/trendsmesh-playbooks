# Template: acceptance report (`<workspace>/acceptance/<YYYY-MM-DD>_<suite>/report_vNN.md`)

Filled by the engine (`tm acceptance report`), never by hand: everything below the line is the
report, with `$name` placeholders (Python `string.Template`) the engine fills from
`acceptance.json` and each case run's `run.json`. The report is saved in the suite's folder and
holds the person's own numbers: they keep it, or send it privately to the TrendsMesh team (contact@trendsmesh.com), never
to a public place. In English. Creative brief spends no money, so this report has no budget,
approval or spend lines.

---

## Acceptance: $suite ($created)

Written $written on $machine with TrendsMesh playbooks $version.

**Results:** $counts.

### Cases

$cases
