---
type: regex
target: { source: file, path: fake-gh/calls.log }
pattern: 'gh issue create -R github\.com/TrendsMesh/trendsmesh-playbooks --title .*CSV.* --body-file - --label enhancement'
---
