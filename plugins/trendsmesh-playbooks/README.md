# TrendsMesh Playbooks

Ready-made marketing workflows ("playbooks") for Claude that turn trends into finished work: refreshed ads, trend
reports, creative briefs, new video ads and short organic videos. You talk to Claude as usual; the playbook decides
the steps, checks its own work, and stops for your yes at the points you choose. Anything that costs money is priced
first and waits for your yes, and every ad it creates in your Meta account starts paused.

## The playbooks

- **Refresh an ad.** Give it a Meta ad that is losing steam. It finds what is rising, then prepares a fresh version:
  a creative brief, an edited video, an AI-made video, or a small live test.
- **Trend research.** Give it a category, such as skincare. It shows which trends to act on now and which are too
  late, in a short report, and every week whether last week's calls held.
- **Creative brief.** Give it a product or a trend you picked. It writes a brief for new ads, with an animatic of
  each idea, on a page you can share.
- **Organic AI videos.** Give it your channel. It proposes videos built on trends; you choose a script to film
  yourself or an AI video, each with a posting kit for every platform.
- **Create an ad.** Give it a product with a website. It makes a new Meta video ad from zero: concept, script,
  stills and video, edit and copy, then offers to create the campaign in your account, paused.
- **Report an issue.** Claude writes up a problem without your account details, shows you the text, and after your
  yes files it on GitHub or sends it privately to TrendsMesh.

## Free or Paid

You choose once, the first time a playbook needs trends; Claude asks first and never starts guessing on its own.

- **Free:** Claude guesses the trends from what it can see (trending tabs, public trend lists, the Meta Ad Library,
  web search) and labels every guess with where it was seen. Trend research is not available on Free.
- **Paid:** Claude reads [TrendsMesh](https://trendsmesh.com)'s always-on trend analysis: hooks, topics, sounds and
  formats repeating across creators, with evidence and a lifecycle stage. It needs a TrendsMesh account on the Agent
  or Swarm plan; sign in once with `/mcp` → trendsmesh → Authenticate.

## Install

```
/plugin marketplace add TrendsMesh/trendsmesh-playbooks
/plugin install trendsmesh-playbooks@trendsmesh-playbooks
```

Then start a session in the folder where you want your work saved and run `/trendsmesh-playbooks:doctor`: it shows
what works, what is missing and what to do about each item. On Windows, install Git for Windows first.

Optional: a Replicate token (AI images and video) and an ElevenLabs key (voices and music), asked for at install and
kept in your system's credential store. The Meta Ads connector is needed for Refresh an ad, Creative brief and
Create an ad.

## What it sends where

The plugin only reaches the services below, and only when a step you started needs them. Everything it makes is
saved in the folder you run Claude from (`runs/` and `library/`).

| Service | When | What goes there |
|---|---|---|
| TrendsMesh MCP (`mcp.trendsmesh.com`) | Paid mode, after you sign in | Your trend searches: category, keywords, market, language. |
| TrendsMesh (`trendsmesh.com/v1/plans`) | When Claude offers Paid | Nothing about you: it reads the public plans and prices. |
| TrendsMesh (`trendsmesh.com/v1/issue-reports`) | Report an issue, after your yes, if you choose to send privately | The issue text you approved, with account details removed. |
| GitHub (`github.com`, through your `gh` command) | Report an issue, after your yes, if you choose GitHub | The same approved text, as a public issue. |
| Meta, through your own Meta Ads connector | Refresh an ad, Creative brief, Create an ad; Ad Library checks | Reads of your ads and the public Ad Library; with your yes, new campaigns, ad sets and ads, created paused. |
| Replicate (`api.replicate.com`) | AI images and video, after you approve the price | Prompts, and the product images or frames a shot is made from. Paid from your Replicate account. |
| ElevenLabs (`api.elevenlabs.io`) | Voices and music, after you approve the price | Script lines, music prompts, and audio for voice or clean-up, when you choose those. Paid from your ElevenLabs credits. |
| Arctic Shift (`arctic-shift.photon-reddit.com`) | Creative brief research | Search terms and a subreddit name, to read public Reddit comments. |
| Mixkit (`mixkit.co`) | Video edits that use stock music or sound effects | Search words for a track or sound; then downloads. |
| Your product's website and Google Fonts | Create an ad | Downloads only: the page, its fonts and logo, drawn in your own Chrome or Edge. |
| Claude artifacts (`claude.ai`) | When you share a page as a link, in the Claude desktop app | The page you chose to share, published privately to your Claude account. |

The tools the playbooks run are installed on first use into the plugin's own data folder, which downloads from
`pixi.sh` and `github.com` (the [pixi](https://pixi.sh) package manager), `conda.anaconda.org`, `pypi.org` and
`files.pythonhosted.org` (Python and ffmpeg; on Windows the plugin's Python is python.org's, from `api.nuget.org`),
and only after your yes for the larger tiers: `download.pytorch.org` and `download-r2.pytorch.org`
and `huggingface.co` (voice and speech models) and `registry.npmjs.org` (Remotion, for video cards, with the headless browser Remotion fetches for itself). These downloads
send nothing about you or your work.

Privacy policy: https://trendsmesh.com/privacy

## What the hooks do

All three hooks run scripts in `bootstrap/`, each in a shell script (`.sh`) for macOS, Linux and Git Bash and a
PowerShell twin (`.ps1`) for Windows without Git Bash. The hook command is one line that both shells read, so the
same `hooks/hooks.json` works on every system.

- **SessionStart** (`session-start.sh` / `.ps1`): installs pixi into the plugin's data folder on first use
  (`install-pixi.sh` / `.ps1`), writes `~/.trendsmesh/paths.json` (three folder paths, no keys) and the session's
  environment variables, and tells Claude about a check-in that is due. It never prints a key.
- **PreToolUse** (`guard-secrets.sh` / `.ps1`): denies a tool call that would read the Replicate or ElevenLabs keys
  (their files, the variables that hold them, or a dump of the whole environment). Local only; it sends nothing.
- **PostToolUse** (`collect-mcp.sh` / `.ps1`): while a playbook run is collecting, saves the TrendsMesh, Ad Library,
  Meta and artifacts answers Claude received into that run's folder (an answer too large to show, from the file
  Claude Code saved it to in this session's own folder). Local only; it sends nothing.

`env/pixi.lock` pins every package of every tool tier on every platform, so each install gets exactly the tested
versions (`pixi run --frozen`). That is why it is larger than the other files.

## Licence

MIT, © TrendsMesh. The source, the full documentation and the issue tracker are at
https://github.com/TrendsMesh/trendsmesh-playbooks.
