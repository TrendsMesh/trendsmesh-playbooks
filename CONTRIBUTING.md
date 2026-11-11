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
   only and moves at release time (`RELEASING.md`); the `Pull request base` check fails a pull request into `main`
   from any branch but `dev` or a `hotfix/` branch.
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

Before every push, issue and pull request from a TrendsMesh machine:

- **Scan the text first.** Write the body of an issue or a pull request to a file, scan it, and only when it prints
  `Scan clean` pass that file on (the title too, if it says anything specific):
  ```
  python3 private/tools/scan.py text body.md
  gh pr create -B dev --title '...' --body-file body.md     # or: gh issue create --title '...' --body-file body.md
  ```
- **Never push with `--no-verify`.** The pre-push hook is the only scan between this checkout and the public
  repository. When it refuses a push, fix the commit (rewrite it so no commit holds the finding), don't skip it.

## Merging

A pull request is never merged with GitHub's merge button (merge, squash or rebase). GitHub writes that commit itself,
under the name and email of the person who clicked, and no scan sees it before it is public. Every commit TrendsMesh
publishes is authored and committed as `TrendsMesh <contact@trendsmesh.com>`.

Instead, after a counted green and only after the owner's yes, the pull request's head is pushed to `dev` from the
TrendsMesh checkout, as a fast-forward:

```
git fetch origin
sha=<the pull request's head commit>             # gh pr view N --json headRefOid --jq .headRefOid
git log --format='%h %an <%ae> | %cn <%ce> | %s' origin/dev.."$sha"   # what dev gains
git push origin "$sha":dev
```

GitHub then shows the pull request as merged. The pre-push hook scans every commit `dev` gains. Git refuses the push
if it isn't a fast-forward: rebase the branch onto `origin/dev`, push it, wait for a counted green again, then push
its new head. `dev`'s branch protection must let admins push (the owner's setting).

An outside contributor's pull request is merged the same way. Their own name stays on their own commits: the owner
adds them to the data repository's `tools/outside_authors.txt` (one `Name <email>` line, as `git log` prints it),
and the scan accepts that identity while it still scans their messages and files. If their branch is behind `dev`,
we rebase it onto `origin/dev` locally (`gh pr checkout N`, then `git rebase origin/dev`): their commits keep them as
the author, and TrendsMesh, rebasing, becomes the committer. Anything we add to their pull request is our own commit,
as TrendsMesh.

The same goes for `main`: it moves only by a fast-forward push of a scanned commit (`RELEASING.md`), never by a
merge on GitHub.
