---
type: regex
target: { source: file, path: runs/01-refresh-ad/2026-11-05_ad/03_wip/decisions/db_list_v01.json }
# the page's read reaches the run: saved by the collector (refresh-ad collects since issue 128), or with ingest
pattern: '"_tool":\s*"db_list"'
---
