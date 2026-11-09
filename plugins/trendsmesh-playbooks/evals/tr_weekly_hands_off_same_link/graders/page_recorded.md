---
type: regex
target: { source: file, path: runs/04-trend-research/2026-11-04_beauty/run.json }
# what tm page published writes (tm.page.record_published): "pages": {"report": {"slug": ...}}
pattern: '"pages"\s*:\s*\{\s*"report"\s*:\s*\{[^{}]*"slug"\s*:\s*"art_mock_1"'
---
