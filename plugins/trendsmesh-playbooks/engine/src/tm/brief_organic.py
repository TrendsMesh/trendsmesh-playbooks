"""The organic video brief of playbook 02 (issue #136): what it holds beside the ad brief's checks.

    channel_gap(run)          the step check `channel_context_written` (O2): `01_base/channel_context.md`,
                              recorded in the manifest with what it rests on
    posting_problems(brief)   the publisher view (O7): each concept's `posting` block per channel platform, its text
                              as pasted held to `data/organic-video/platform_rules.yaml`, as `tm kit check` holds a
                              posting kit (`tm.kit`: the length, the hashtags, no link, no engagement bait)
    plan_problems(brief)      the posting plan (O8's input, written at O7): each post a concept and a platform of
                              the channel on a day and a time; the measures views, % watched to the end, saves and
                              shares, each target with its source (R3), null when there is no channel data
    seed_rows(run, brief, concept_ids)   the `seed/1` rows (`source: pb2`) `tm brief handoff --to-video` writes

A brief is organic when `meta.kind` is `organic` (`brief_checks` routes its stages here).
"""

from __future__ import annotations

import re
from datetime import date

from tm import kit, manifest
from tm.config import Problem
from tm.runfolder import RunFolder

CHANNEL_CONTEXT = "01_base/channel_context.md"
METRICS = ("views", "completion_rate", "saves", "shares")
METRIC_LABEL = {"views": "views", "completion_rate": "% watched to the end", "saves": "saves", "shares": "shares"}
POSTING_FIELDS = ("description", "post_time", "sound")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _filled(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def channel_gap(run: RunFolder) -> str | None:
    """O2 is done once the channel context is written and recorded with its sources (`tm record`, or `tm page
    fetch` for the page it rests on)."""
    path = run.path / CHANNEL_CONTEXT
    if not path.is_file() or not path.read_text(encoding="utf-8-sig").strip():
        return (f"the channel context is written as {CHANNEL_CONTEXT} (what the channel films, its topic, audience "
                "and style, from organic video's saved channel, its page or the user's description)")
    rows = [r for r in manifest.rows(run) if r["file"] == CHANNEL_CONTEXT and _filled(r.get("source"))]
    if not rows:
        return (f"{CHANNEL_CONTEXT} is recorded with what it rests on (tm record --run R --file {CHANNEL_CONTEXT} "
                "--stage 01_base --source \"<the channel page, the saved channel or the user's description>\")")
    return None


def platforms(brief: dict) -> list[str]:
    """The channel's platforms, as the brief names them (meta.channel.platforms)."""
    got = ((brief.get("meta") or {}).get("channel") or {}).get("platforms")
    return [p for p in got if isinstance(p, str)] if isinstance(got, list) else []


def pasted(name: str, block: dict) -> str:
    """The text the publisher pastes on a platform: the description with the hashtags it does not hold yet."""
    return kit._with_hashtags(str(block.get("description") or ""), kit._strings(block.get("hashtags")))


def posting_problems(brief: dict) -> list[Problem]:
    """The publisher view: every concept has a `posting` block for each of the channel's platforms, with the
    description, the hashtags, the posting time and the sound, and its text as pasted keeps the platform's rules."""
    out: list[Problem] = []
    wanted = platforms(brief)
    for i, c in enumerate(brief["concepts"]):
        cid, posting = c["id"], c.get("posting") or {}
        for name in wanted:
            where = f"concepts[{i}].posting.{name}"
            block = posting.get(name)
            if not isinstance(block, dict):
                out.append(Problem(f"concepts[{i}].posting", f"{cid} has no posting for {name}, one of the channel's "
                                   "platforms (the publisher view).",
                                   f"Write {name}'s description, hashtags, post_time and sound."))
                continue
            for field in POSTING_FIELDS:
                if not _filled(block.get(field)):
                    out.append(Problem(f"{where}.{field}", f"{cid}'s posting for {name} has no {field}.",
                                       f"Give its {field.replace('_', ' ')}."))
            if name == "youtube" and not _filled(block.get("title")):
                out.append(Problem(f"{where}.title", f"{cid}'s YouTube posting has no title.", "Give the title."))

            def bad(field: str, what: str, todo: str, _cid=cid) -> None:
                out.append(Problem(field, f"{_cid}: {what}", todo))
            text = pasted(name, block)
            kit._hashtag_count(bad, f"{where}.hashtags", name, text)
            if name == "youtube":
                kit._too_long(bad, f"{where}.description", name, "description", text, "description_max")
                title = str(block.get("title") or "")
                if len(title) > kit.YOUTUBE_TITLE_MAX:
                    bad(f"{where}.title", f"the YouTube title is {len(title)} characters; it takes at most "
                        f"{kit.YOUTUBE_TITLE_MAX}.", f"Shorten it to {kit.YOUTUBE_TITLE_MAX}.")
            else:
                kit._too_long(bad, f"{where}.description", name, "text", text, "text_max")
            for field in ("description", "title"):
                if _filled(block.get(field)):
                    kit._post_text(lambda f, w, t: bad(f, w.lower().replace("the text", f"the {field}"), t),
                                   f"{where}.{field}", block[field])
        extra = [p for p in posting if p not in wanted]
        if extra:
            out.append(Problem(f"concepts[{i}].posting", f"{cid} has posting for {', '.join(extra)}, which is not one "
                               f"of the channel's platforms ({', '.join(wanted)}).",
                               "Leave out the platforms the channel does not post on."))
    return out


def seed_rows(run: RunFolder, brief: dict, concept_ids: list[str], cfg: dict, *, page_ref: dict | None,
              today: date | None = None) -> list[dict]:
    """The `seed/1` rows (`source: pb2`) of the concepts handed to organic video (O8), as `tm.seeds` describes
    them: the concept's trend (null in a guess run), the run's category and market (config), the trend research
    seed's bucket and band when the brief started from one, and the concept itself."""
    from tm import library, seeds, trend_spool      # seeds imports the trend research modules: only here
    workspace = trend_spool.workspace_of(run)
    name = run.path.resolve().name
    run_rel = run.path.resolve().relative_to(workspace).as_posix()
    category = (cfg.get("product") or {}).get("category_phrase")
    market = (cfg.get("account") or {}).get("market") or brief["meta"].get("market")
    started = cfg.get("seed")
    origin = next((r for r in library.read_jsonl(workspace / seeds.FILE)[0]
                   if started and r.get("seed_id") == started), {}) if started else {}
    concepts = {c["id"]: c for c in brief["concepts"]}
    out = []
    for cid in concept_ids:
        c = concepts[cid]
        trend = (c.get("plugin") or {}).get("trend") or {}
        organic = c.get("organic") or {}
        tid = trend.get("trend_id")
        out.append({
            "schema": seeds.SCHEMA, "seed_id": f"{name}:{c['brief_id']}", "source": seeds.PB2, "run": name,
            "created": (today or date.today()).isoformat(), "category": category,
            "sub_category": origin.get("sub_category") or category, "market": market,
            "trend_id": tid, "kind": trend.get("kind"), "trend_name": trend.get("name"),
            "bucket": origin.get("bucket") or "brief", "band": origin.get("band"), "paid_level": seeds.NOT_CHECKED,
            "angle": c.get("one_liner"), "risk": (c.get("decision_facts") or {}).get("risk"),
            "valid_until": brief["meta"]["valid_until"], "report": page_ref,
            "evidence": f"{run_rel}/02_research/videos/{tid}*.json" if tid else "",
            "brief_id": c["brief_id"], "concept": cid, "hook": (c.get("hook") or {}).get("text"),
            "topic": organic.get("topic"), "format": organic.get("format"), "length_s": organic.get("length_s"),
            "sound": organic.get("sound")})
    return out


def plan_problems(brief: dict) -> list[Problem]:
    """The posting plan (`plan`): which concept on which platform, the day and the time, and the organic measures
    with their targets and sources (R3)."""
    out: list[Problem] = []
    plan = brief.get("plan") or {}
    ids = [c["id"] for c in brief["concepts"]]
    wanted = platforms(brief)
    posts = plan.get("posts") or []
    if not posts:
        out.append(Problem("plan.posts", "The posting plan has no posts.",
                           "Say which concept goes on which platform, the day and the time."))
    for k, post in enumerate(posts):
        where = f"plan.posts[{k}]"
        if post.get("concept") not in ids:
            out.append(Problem(f"{where}.concept", f"The plan posts {post.get('concept')!r}, which is not a concept of "
                               f"the brief ({', '.join(ids)}).", "Name a concept of the brief."))
        if post.get("platform") not in wanted:
            out.append(Problem(f"{where}.platform", f"The plan posts on {post.get('platform')!r}, which is not one of "
                               f"the channel's platforms ({', '.join(wanted)}).", "Name one of the channel's platforms."))
        try:
            date.fromisoformat(str(post.get("date")))
        except ValueError:
            out.append(Problem(f"{where}.date", f"The plan's date {post.get('date')!r} is not a day (YYYY-MM-DD).",
                               "Give the day it is posted."))
        if not _TIME.fullmatch(str(post.get("time") or "")):
            out.append(Problem(f"{where}.time", f"The plan's time {post.get('time')!r} is not a time (HH:MM).",
                               "Give the time it is posted, as 18:00."))
    metrics = plan.get("metrics") or []
    named = [m.get("name") for m in metrics]
    missing = [m for m in METRICS if m not in named]
    if missing:
        out.append(Problem("plan.metrics", f"The posting plan does not measure {', '.join(missing)} (an organic "
                           f"brief measures {', '.join(METRIC_LABEL[m] for m in METRICS)}).",
                           "Add each, with its target and source, or a null target \"to set\"."))
    for k, m in enumerate(metrics):
        if not _filled(m.get("source")):
            out.append(Problem(f"plan.metrics[{k}].source", f"The measure {m.get('name')!r} has no source (R3): a "
                               "target says where it comes from, and none says why it is to set.",
                               "Give its source (the channel's own numbers, or \"to set: no channel data\")."))
    return out
