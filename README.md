# TrendsMesh Playbooks

A plugin for [Claude Code](https://claude.com/claude-code) with ready-made marketing workflows ("playbooks") that turn
trend data from [TrendsMesh](https://trendsmesh.com) into finished work: refreshed ads, trend reports, creative
briefs and short videos. You talk to Claude as usual; the playbook decides the steps, checks its own work, and stops
for your yes at the points you choose.

## The playbooks

- **Refresh an ad.** Give it an ad that is losing steam. It finds what is rising on TikTok and similar places, then
  prepares a fresh version of your ad: a creative brief, an edited video, an AI-made video, or a small live test.
  Every ad it creates starts **paused**, and goes live only when you approve the launch (or, in Hands-off, within
  the test budget you set at the start).
- **Trend research.** Give it a category, such as skincare or kitchen gadgets. It shows what is moving in that
  category, which trends to act on now, and which are already too late, in a short report you open from a link. Ask
  for the weekly update ("update my trend report"); it also checks whether last week's calls held.
- **Creative brief.** Give it a product, or a trend you picked in a trend report. It writes a brief for new ads: who
  the ad speaks to, in their own words, what the trend adds, and a short animatic of each idea, on a page you can
  share with your team or a client.
- **Organic AI videos.** Give it your channel. It proposes videos from real trends on a page you can share; you
  choose what to make: a script to film yourself, or an AI video. Or say "plan my week of videos" for a weekly pack.
  Each video comes with a posting kit for every platform.
- **Create an ad.** Give it a product with a website. It makes a new video ad for Meta from zero: a concept built on
  a proven ad format and rising trends, the script, the paid stills and video, the edit and the Meta copy, with a
  check-in after each stage. Then it offers to create the campaign, ad set and ad in your account, **paused**; it
  never switches them on. It needs the Meta Ads connector, and Replicate and ElevenLabs for the paid parts;
  TrendsMesh is optional (without it, the trends are labelled as guesses).
- **Report an issue.** Say "report this problem" or "I'd like a change": Claude writes it up without your account
  details, shows you the exact text, and after your yes files it on GitHub or sends it privately to TrendsMesh.

## What you need

- **Claude Code**, in the terminal or the Claude desktop app. It needs a paid Claude plan (Pro, Max, Ultra, Team or
  Enterprise) or an Anthropic Console account: the free Claude plan does not include Claude Code.
- **On Windows: Git for Windows**, installed before the plugin. Claude Code fetches the plugin from GitHub with Git,
  so without it the install fails. In PowerShell or a terminal: `winget install --id Git.Git -e` (or download it from
  https://git-scm.com/downloads/win), then restart Claude Code. With Git installed you also no longer see the notice
  at the start of each session that Git Bash wasn't found and a hook ran in PowerShell. That notice is harmless:
  the plugin's hooks work in PowerShell too.
- A **TrendsMesh** account on the **Agent** or **Swarm** plan, so Claude can read the trends. The plugin brings the
  TrendsMesh connector; sign in once with `/mcp` → trendsmesh → Authenticate (the doctor walks you through it).
  Trend research and organic video need it. Refresh an ad and creative briefs run without it, and label their trend
  claims as guesses.
- The **Meta Ads connector** in Claude Code, signed in to your ad account: needed for refresh an ad and creative
  briefs. Trend research uses it, when it is there, to check the public Meta Ad Library.
- **Chrome or Edge**, to draw the animatics and animation videos.
- Only for AI video and voices: a **Replicate** token and an **ElevenLabs** key. A script to film needs neither.
- Optional: **Claude Code in the Claude desktop app**, which brings the claude.ai artifacts tools, to share pages as
  links. Without it you get files.

## Install

Paste this into Claude Code:

> Install the TrendsMesh playbooks plugin for me: add the marketplace `TrendsMesh/trendsmesh-playbooks`, then install
> the plugin `trendsmesh-playbooks` from it.

Or type the two commands yourself:

```
/plugin marketplace add TrendsMesh/trendsmesh-playbooks
/plugin install trendsmesh-playbooks@trendsmesh-playbooks
```

When you install with `/plugin install` in a Claude Code session, it asks for the Replicate token and the
ElevenLabs key. Leave them empty if you do not want AI video or voices. It does not ask when the plugin was installed
another way, for example with `claude plugin install` in a terminal (which says the options are "not yet set"). To
add or change them later, in a Claude Code session: `/plugin` → **Installed** → trendsmesh-playbooks →
**Configure options** (or type `/plugin configure trendsmesh-playbooks@trendsmesh-playbooks`), then start a new
session.

## Use it

1. Start a normal Claude Code session in the folder where you want your work saved (not a one-line `claude -p`
   command, which cannot ask you for approval).
2. Check that everything is ready: `/trendsmesh-playbooks:doctor`. It shows what works, what is missing, and what to
   do about each item.
3. Then just say what you want:
   - **"Refresh my fading ad."** Claude asks which ad account and ad, shows what it found, and stops for your yes
     where you chose: **Check every step**, **Just the big calls** or **Hands-off**.
   - **"What is moving in skincare?"** (your own category). Later: **"update my trend report"**.
   - **"Write a creative brief for my product"**, or after a trend report, **"turn my trend pick into a brief"**.
   - **"Video ideas for my channel"**, **"a script I can film"** or **"plan my week of videos"**.
   - **"Make me a Meta video ad for my product"** (with its website). Claude asks four questions first: who the ad
     is for, what it sells, how long it runs and where, and which files you already have.

### Money and safety

- Anything that costs money (AI video, images, voices) is priced first and waits for your yes; organic video also
  shows when each price was checked. A take that fails without output costs nothing.
- Ads it creates in your Meta account start **paused**. They go live when you approve the launch. In **Hands-off**
  you set the budgets once at the start: Claude launches and spends within them, and reports after.
- Your keys stay in your system's credential store and in a file readable only by you, in the plugin's data folder.
  They are never printed or written into your project.

### Where your work goes

Everything is saved in the folder you run Claude from. `runs/` holds one folder per refresh, trend report, brief or
video, with every file it made; nothing is overwritten (new versions get `_v02`, `_v03`, ...). `library/` keeps what
carries over between runs: results of each refresh, trend calls (checked the week after), picks handed on to a
brief, briefs handed on to a refresh, and each brand's and channel's profile. The doctor's support report
(`trendsmesh-support-<date>.md`) and acceptance runs (`acceptance/`) are saved there too.

### What it installs

On first use the plugin installs [pixi](https://pixi.sh) and its basic tools (about 0.5 GB) into its own data
folder; your system Python, PATH and settings are left alone. Bigger tools, such as the video breakdown tools (about
2.5 GB), are installed only after you say yes, with their size shown first. Outside its data folder it writes one
small file, `~/.trendsmesh/paths.json` (three folder paths, no keys), and pixi keeps its usual shared download cache.

These installs need the internet. Behind a firewall or proxy, or in an app that limits which sites Claude may
reach, allow `pixi.sh`, `pixi.prefix.dev`, `github.com` and `release-assets.githubusercontent.com` (pixi itself),
and `conda.anaconda.org`, `pypi.org` and `files.pythonhosted.org` (the tools). If an install fails, Claude tells you
the reason and where its log is; running `/trendsmesh-playbooks:doctor` tries it again.

## Report a problem

Open an issue in this repository. Describe what you asked for and what happened. **Do not paste ad account ids,
spend, keys or tokens** into an issue: issues are public. The doctor's support report can hold such details from
your runs: read it first, and send it privately to contact@trendsmesh.com rather than attaching it to an issue.

## For developers

The plugin is `plugins/trendsmesh-playbooks/`: skills, the `doctor` and `acceptance` commands, hooks,
`bootstrap/`, the Python engine in `engine/src/tm/`, the pixi environments in `env/`, the video card templates in
`remotion/`, the animation style library in `data/styles/` and the evals in `evals/`. The marketplace file is
`.claude-plugin/marketplace.json`.

Try it from a local folder, without installing:

```
claude --plugin-dir plugins/trendsmesh-playbooks
```

Run the tests (needs [pixi](https://pixi.sh)):

```
cd plugins/trendsmesh-playbooks/env
pixi run --frozen -e dev test                            # engine tests
sh ../bootstrap/test-bootstrap.sh && sh ../bootstrap/test-guard-secrets.sh   # macOS, Linux, Windows (Git Bash)
../bootstrap/test-bootstrap.ps1                          # Windows (PowerShell)
pixi run --frozen -e dev-full test-tools                 # heavy tiers: breakdown, video, voice
```

Some engine tests check the plugin against reference runs that are not published; they are marked `private_data`
and skip here. The evals (`evals/run.sh`) drive Claude through scripted scenarios with mocked services; they call the
Claude API and cost a little. CI runs the engine and bootstrap tests on Ubuntu, Windows and macOS for every push.

Changes per version: [CHANGELOG.md](CHANGELOG.md).

## Licence

The playbooks in this repository are under the [MIT licence](LICENSE), © TrendsMesh. It covers this repository only:
not the TrendsMesh name or the TrendsMesh service whose data the plugin reads, which has its own terms. Tools the
plugin uses keep their own licences.

The opening and ending cards of edited videos are made with [Remotion](https://www.remotion.dev), which has its own
licence: as we read it, individuals, non-profits and companies with up to 3 employees can use it free; larger
companies need a Remotion company licence. Check the current terms at
[remotion.dev/license](https://www.remotion.dev/license) before using it commercially. Remotion is not part of
TrendsMesh, and we do not sell or cover its licence.
