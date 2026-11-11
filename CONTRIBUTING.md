# Contributing

The TrendsMesh playbooks plugin is developed here, in the open: issues, changes and releases all happen in this
repository.

## Issues

- Report a bug or ask for a change in an issue here.
- **Never paste account data**: ad account ids and names, spend, results, client or customer texts, emails, tokens
  or keys. Instead of copying logs, ask Claude to report the problem: the plugin's `report-issue` skill writes the
  report, takes the private data out, shows you the exact text and sends it only after your yes, publicly here or
  privately to TrendsMesh.
- An acceptance report (`/trendsmesh-playbooks:acceptance`) is never a public issue: send it privately, as the
  command says.

## Pull requests

1. Branch from `dev`, and open the pull request into `dev`: `gh pr create -B dev`. `main` holds released versions
   only and moves at release time (`RELEASING.md`).
2. Add a bullet for your change under `## Unreleased` in `CHANGELOG.md`, in its style: one bullet per change, with
   a bold lead. A pull request that changes `plugins/` without it fails the `Changelog` check, unless it carries
   the `no-changelog` label (for a change users won't notice).
3. Run the tests: from `plugins/trendsmesh-playbooks/env`, `pixi run --frozen -e dev test`.
4. Fill in the pull request template, ticking each line you checked.

Tests that need private data are marked `private_data`; without that data they are skipped, so the suite runs
anywhere.

## On TrendsMesh machines

The private data repository (the test data, the tester's handoff packages and the leak scanner) is cloned as
`private/` inside this checkout, then set up:

```
git clone <the private data repository> private
private/tools/install-hooks.sh
```

`install-hooks.sh` sets this checkout's commit identity to TrendsMesh, installs a pre-push hook that runs the leak
scanner on everything being pushed, and links the private data into place, git-ignored. Run it again after
`private/LINKS` changes. A push from a checkout that has `private/` but not the hook is a mistake: the test run
fails until the hook and the links are in place.
