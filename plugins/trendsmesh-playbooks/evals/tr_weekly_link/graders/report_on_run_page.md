---
type: regex
target: { source: file, path: runs/04-trend-research/2026-11-04_beauty/04_final/report_v01/index.html }
# issue #60: the report is on the shared run page: its top bar with the playbook's name, the report's views, and
# under them the check-ins already recorded (in this Hands-off run, by rule), read-only (no input anywhere)
pattern: '<span class="pill dark">Trend research</span>(?![\s\S]*<input)[\s\S]*id="view-report"[\s\S]*<section class="settled">[\s\S]*by rule'
---
