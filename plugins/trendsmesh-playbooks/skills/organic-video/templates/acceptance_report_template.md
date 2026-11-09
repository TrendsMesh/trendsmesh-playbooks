# Template: acceptance report (`<workspace>/acceptance/<YYYY-MM-DD>_<suite>/report_vNN.md`)

Filled by the engine (`tm acceptance report`), never by hand: everything below the line is the
report, with `$name` placeholders (Python `string.Template`) the engine fills from
`acceptance.json` and each case run's `run.json`. The report is saved in the suite's folder and
holds the person's own numbers: they keep it, or send it privately to the TrendsMesh team (contact@trendsmesh.com), never
to a public place. In English.

---

## Acceptance: $suite ($created)

Written $written on $machine with TrendsMesh playbooks $version.

**Results:** $counts.

**Suite budget:** $approval

### Cases

$cases

### Spend against the suite budget

$totals

Every case run's spend is read from its own `run.json`; a refused prediction (O8) adds nothing.
The week's total (O9) counts a dropped day's spend.
Nothing in this suite spends money on Meta ads.
