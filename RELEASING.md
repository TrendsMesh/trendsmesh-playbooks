# Releasing

How a change becomes a release of the TrendsMesh playbooks plugin. Claude Code installs from this repository's
default branch, and users get new files only when `version` changes, so:

- **`main`** is the default branch and holds released versions only. It moves at release time, by a fast-forward to
  `dev`. Only the repository admins can push to it.
- **`dev`** is where every pull request goes, with green CI and a bullet under `## Unreleased` in `CHANGELOG.md`
  (the `Changelog` workflow checks it). Pull requests target `dev`: the `Pull request base` workflow fails a pull
  request into `main` unless its branch is `dev` or starts with `hotfix/`.
- **Merging is a fast-forward push, never GitHub's merge button**, which writes its own commit under the clicking
  person's name and email, unseen by any scan. After a counted green and the owner's yes, from the TrendsMesh
  checkout: `git fetch origin && git push origin <pr-head-sha>:dev`, and GitHub shows the pull request as merged
  (`CONTRIBUTING.md`, "Merging", has the steps). `dev`'s protection must let admins push. `main` moves the same way:
  a fast-forward push of the scanned commit.
- **Every push, tag and release only after the owner's yes.** An agent prepares each step and waits for that yes
  before it pushes, merges, tags or publishes anything. Each such step below says so again.
- **Pushing a tag publishes its release.** The `Release` workflow (`.github/workflows/release.yml`) creates the
  GitHub release for every pushed `vX.Y.Z` or `vX.Y.Z-rc.N` tag, as github-actions[bot], so no person's account
  is named as its author. Before publishing it checks that the version in the four places below is the tag's,
  that a release candidate's commit is on `dev` and a release's commit is `main`, and that the tag has no release
  yet; any failed check stops it with nothing published. Its notes are the changelog section being released, read
  from `CHANGELOG.md` at the tagged commit. Never run `gh release create` by hand.

The version is in four places, always changed together in one commit:

- `plugins/trendsmesh-playbooks/.claude-plugin/plugin.json` (`"version"`)
- `plugins/trendsmesh-playbooks/engine/pyproject.toml` (`version`)
- `plugins/trendsmesh-playbooks/engine/src/tm/__init__.py` (`__version__`)
- `plugins/trendsmesh-playbooks/engine/tests/test_cli.py` (the expected `tm X.Y.Z`)

Version numbers: the minor version for a batch of fixes and features (0.10.0, 0.11.0); the patch version for a fix
to a release (0.10.1). Changelog headings are the bare version: `## X.Y.Z`.

The scan commands below need `private/`, the private data repository, cloned and set up as `CONTRIBUTING.md` says.

## One-time setup

The `no-changelog` label must exist before a pull request can carry it. Create it once, only after the owner's yes:

```
gh label create no-changelog -R TrendsMesh/trendsmesh-playbooks --description "Changes nothing a user sees"
```

## Before every tag

Run these in the shell you tag from: the tag goes on exactly the commit that was scanned.

1. Bring the checkout up to date: `git fetch origin`
2. Fix the commit to release: `sha=$(git rev-parse origin/dev)` (for a hotfix, `origin/hotfix/X.Y.Z`).
3. Scan it: `python3 private/tools/scan.py tree . "$sha"`. It must print `Scan clean`. Any finding stops the release.
4. Check what the `Release` workflow will check, on that commit, and read the notes it will publish:
   ```
   git switch --detach "$sha"
   notes=$(mktemp) && python3 .github/scripts/release.py prepare vX.Y.Z-rc.N . "$notes" && cat "$notes"
   git switch -
   ```
   It must print the version, then the section being released (for a release candidate, `## Unreleased`; for a
   release, `## X.Y.Z`). The scan in step 3 has already read the notes, since they are in `CHANGELOG.md`.
5. Check by hand what the scan prints under "Check by hand".

## Release candidate X.Y.Z-rc.N

1. **Version pull request.** On a branch from `dev`, set the version to `X.Y.Z-rc.N` in the four places and commit
   "Release X.Y.Z-rc.N". The changelog stays under `## Unreleased` until the release, so the pull request carries
   `no-changelog`. Only after the owner's yes, push the branch and open it:
   `gh pr create -B dev --title "Release X.Y.Z-rc.N" --label no-changelog`. Merge it after a counted green, only
   after the owner's yes, by pushing its head to `dev` (`CONTRIBUTING.md`, "Merging").
2. **Check:** the steps under "Before every tag", which set `$sha` to the merged `dev`.
3. **Tag** that commit, and push the tag only after the owner's yes. The push publishes the pre-release:
   ```
   git tag vX.Y.Z-rc.N "$sha"
   git push origin vX.Y.Z-rc.N
   ```
4. **Watch the release run**: `gh run watch -R TrendsMesh/trendsmesh-playbooks "$(gh run list -R TrendsMesh/trendsmesh-playbooks --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')"`.
   It must end in success, and `gh release view vX.Y.Z-rc.N -R TrendsMesh/trendsmesh-playbooks` shows the
   pre-release. If it failed, read why in its log, fix the cause, and run it again only after the owner's yes:
   `gh workflow run release.yml -R TrendsMesh/trendsmesh-playbooks -f tag=vX.Y.Z-rc.N`. A fix that needs a new
   commit needs a new tag (the next `rc.N`): never move a pushed tag.
5. Ask the tester to check it, with the steps below.

### The tester's check of a release candidate

A user can register only one marketplace by a name, and `main` and the release candidate both call theirs
`trendsmesh-playbooks`. So the tester swaps the marketplace for the candidate's, in Claude Code:

1. `/plugin marketplace remove trendsmesh-playbooks`
2. `/plugin marketplace add TrendsMesh/trendsmesh-playbooks#vX.Y.Z-rc.N`
3. `/plugin install trendsmesh-playbooks@trendsmesh-playbooks`
4. Start a new session.
5. Run `/trendsmesh-playbooks:acceptance`, and send the report privately, as it says.

Afterwards, back to the released version, the same swap the other way:

1. `/plugin marketplace remove trendsmesh-playbooks`
2. `/plugin marketplace add TrendsMesh/trendsmesh-playbooks`
3. `/plugin install trendsmesh-playbooks@trendsmesh-playbooks`
4. Start a new session.
5. Run `/trendsmesh-playbooks:doctor`: its `tm engine` line shows the released version.

Adding a marketplace at a tag is the documented `owner/repo#ref` form. That it also takes the plugin's files from
that tag (the plugin's source is a path inside this repository) is proven at the first release candidate: in step
5 of the check, `/trendsmesh-playbooks:doctor` shows the candidate's version on its `tm engine` line. If it doesn't
take the tag's files, release candidates move to an `rc` branch instead of a tag (`#rc` in step 2), and the rest
stays the same.

A finding goes into an issue and a fix into `dev`; the next candidate is `X.Y.Z-rc.N+1`.

## Release X.Y.Z

1. **Version pull request.** On a branch from `dev`, set the version to `X.Y.Z` in the four places and turn
   `## Unreleased` in `CHANGELOG.md` into `## X.Y.Z`. Commit "Release X.Y.Z". Only after the owner's yes, push the
   branch and open it: `gh pr create -B dev --title "Release X.Y.Z"`. Merge it after a counted green, only after
   the owner's yes, by pushing its head to `dev` (`CONTRIBUTING.md`, "Merging").
2. **Check:** the steps under "Before every tag", which set `$sha` to the merged `dev`. The notes are the
   `## X.Y.Z` section.
3. **Move `main`** to that commit, as a fast-forward, only after the owner's yes:
   ```
   git push origin "$sha":main
   ```
   Git refuses the push if it isn't a fast-forward: then stop and find out why `main` has moved. Never force it,
   and never move `main` with a merge on GitHub.
4. **Tag** the same commit, and push the tag only after the owner's yes. The push publishes the release:
   ```
   git tag vX.Y.Z "$sha"
   git push origin vX.Y.Z
   ```
5. **Watch the release run**, as for a release candidate (step 4 there), with `vX.Y.Z`.
6. Add a new `## Unreleased` heading to `CHANGELOG.md` with the next pull request into `dev`.

Users get the release on their next `/plugin marketplace update`, or when Claude Code starts if they switched
auto-update on.

## Hotfix: a fix to a release

- **`dev` holds no unreleased work:** fix it on `dev` with an ordinary pull request, then release the patch version
  as above (a release candidate first unless the owner says otherwise).
- **`dev` already holds unreleased work:**
  1. Cut a branch from the release being fixed: `git switch -c hotfix/X.Y.Z vX.Y.Z`
  2. Commit the fix, with the patch version (`X.Y.Z+1`) in the four places and its `## X.Y.Z+1` section in
     `CHANGELOG.md`. Push the branch only after the owner's yes: `git push origin hotfix/X.Y.Z`
  3. CI runs on `main` and `dev` only, so run it on the branch by hand, and wait for a counted green:
     `gh workflow run ci.yml --ref hotfix/X.Y.Z`
  4. The steps under "Before every tag", with `sha=$(git rev-parse origin/hotfix/X.Y.Z)`.
  5. Move `main`, tag and release that commit as in steps 3 to 5 above, each only after the owner's yes:
     `git push origin "$sha":main`, `git tag vX.Y.Z+1 "$sha"` and `git push origin vX.Y.Z+1`, which publishes the
     release; then watch the release run.
  6. Merge the fix back into `dev`, as a fast-forward of `dev`. On a branch from `dev`, merge the hotfix locally,
     keeping `dev`'s `## Unreleased` section above the hotfix's section (the merge commit is TrendsMesh's own):
     ```
     git fetch origin
     git switch -c hotfix-X.Y.Z+1-into-dev origin/dev
     git merge --no-ff origin/hotfix/X.Y.Z -m "Hotfix X.Y.Z+1 into dev"
     ```
     Only after the owner's yes, push it and open the pull request:
     `gh pr create -B dev --title "Hotfix X.Y.Z+1 into dev"`. After a counted green and the owner's yes, push its
     head to `dev` (`git push origin "$(git rev-parse HEAD)":dev`, a fast-forward). Delete both branches once
     it's merged.
