"""Creative brief on the shared run page (issue #60): its stage materials and outcomes (`COMPONENTS`, `OUTCOMES`),
its check-ins' names (`run_page.creative_brief.stage.<id>`), and the frame `tm brief page` puts around the brief (`frame`).

    materials(ctx, checkin)          a settled check-in's materials: the concepts chosen (G2), and the team's decisions
                                     as read from the page (G2, G3, G4: each concept's verdict, every note whole)
    outcome(ctx, checkin, choice)    the decision in words ("C1, C3 chosen", "Accepted")
    name(ctx, checkin)               the check-in's name in the page's language (the frame's; the run page's
                                     own lookup reads the same key)
    frame(run, lang)                 the check-in the page is up for, and the "Already settled" group, as HTML

The brief's page stays a team page: everyone with the link reads the decisions and each person saves their own
(`decisions/{self}`, tm.brief_page), so its decision forms are the brief's own, never the run page's owner-only block.
What the shared page gives it is the rest: the look (`assets/page/`), the top bar, the "Now" block and the "Already
settled" group (tm.run_page.template), their words (the table's `run_page` area; the brief's in `brief`), and the
settled check-ins as read-only summaries from run.json, with no input, so an earlier decision cannot be saved again.
The settled group is never in the creator's view (CB13: it holds the team's notes and the run's decisions).
"""

from __future__ import annotations

from datetime import datetime

from tm import checkins, state, trends
from tm.run_page import template, words
from tm.run_page.context import Context

PAGE_STAGES = ("G2", "G3", "G4")                 # decided on the page (tm.brief_page.STAGES)
DECIDING = ("decision", "strategy", "media-buyer")  # the views that decide; the creator's shows no decision
CARDS = {"approve_setup": "brief.card_approve_setup", "approve_briefs": "brief.card_approve_briefs"}
VERDICTS = {"approved": "brief.verdict_approved", "changes": "brief.verdict_changes", "split": "brief.verdict_split",
            "none": "brief.verdict_none"}
CHOSEN = {"page": "brief.chosen_page", "chat": "brief.chosen_chat", "rule": "brief.chosen_rule"}
CHOICES = {"approve": "brief.approved", "change": "brief.changes_requested"}


def _w(key: str, lang: str, **values: object) -> str:
    return words.tx(key, lang, **values)


def name(ctx: Context, checkin: str) -> str:
    """The check-in's name: `run_page.creative_brief.stage.<id>` (Creative brief's G2 is not Refresh an ad's
    `run_page.stage.G2`), else the catalogue's."""
    known = checkins.load(playbook=state.load(ctx.run).playbook).checkins.get(checkin)
    return ctx.t_or(f"creative_brief.stage.{checkin}", known.name if known else checkin)


def _chosen(run) -> dict:
    chosen = (state.load(run).brief or {}).get("chosen") or {}
    return chosen if isinstance(chosen, dict) and isinstance(chosen.get("concepts"), list) else {}


def outcome(ctx: Context, checkin: str, choice: object) -> str | None:
    if choice != "accept":
        return None
    concepts = _chosen(ctx.run).get("concepts") if checkin == "G2" else None
    if concepts:
        return _w("brief.outcome_chosen", ctx.lang, concepts=", ".join(map(str, concepts)))
    return _w("brief.outcome_accepted", ctx.lang)


def _read(run, stage: str) -> tuple[str, dict] | None:
    """The latest decisions file `tm brief decisions` read for `stage`: (run-relative path, its data)."""
    from tm import brief_page          # brief_page builds its page with this module
    files = [f for f in brief_page._decisions_files(run) if f.name.startswith(f"decisions_{stage}_")]
    if not files:
        return None
    try:
        data = trends.read(files[-1])
    except (OSError, ValueError):
        return None
    return (files[-1].relative_to(run.path).as_posix(), data) if isinstance(data, dict) else None


def materials(ctx: Context, checkin: str) -> list[dict]:
    lang, out = ctx.lang, []
    chosen = _chosen(ctx.run) if checkin == "G2" else {}
    if chosen.get("concepts"):
        source = CHOSEN.get(chosen.get("source"))
        out.append({"kind": "text", "text": _w("brief.settled_chosen", lang,
                                               concepts=", ".join(map(str, chosen["concepts"])),
                                               source=_w(source, lang) if source else str(chosen.get("source") or ""))})
    found = _read(ctx.run, checkin) if checkin in PAGE_STAGES else None
    if found is None:
        return out
    rel, data = found
    verdicts = data.get("verdicts") if isinstance(data.get("verdicts"), dict) else {}
    lines = []
    for cid, v in verdicts.items():
        key = VERDICTS.get(v.get("verdict")) if isinstance(v, dict) else None
        if key:
            lines.append(_w(key, lang, id=cid, approve=v.get("approve") or 0, change=len(v.get("change") or [])))
    for cid in verdicts:                      # every note whole (issue #55), by concept, then person
        for d in data.get("docs") or []:
            x = ((d.get("decisions") or {}).get(cid) if isinstance(d, dict) else None) or {}
            note = x.get("n") if isinstance(x, dict) else None
            if x.get("d") in CHOICES and isinstance(note, str) and note.strip():
                lines.append(_w("brief.settled_note", lang, id=cid, who=d.get("who"), choice=_w(CHOICES[x["d"]], lang),
                                note=note))
    out.append({"kind": "text", "text": _w("brief.settled_read", lang, file=rel)})
    if lines:
        out.append({"kind": "list", "items": lines})
    return out


def frame(run, lang: str) -> dict:
    """What `tm brief page` puts around the brief: `{stage, settled, updated, run}`. `stage` is the check-in the page
    is up for (`{key, n, name}`, its card's name at Just the big calls), None when none is decided on the page now
    (all are settled, the run makes the review pack alone, or Hands-off decides by rule); `settled` is the "Already
    settled" group's HTML (newest first), empty when nothing is decided yet."""
    from tm.run_page import _latest_decisions, _record     # the run page builds its page with this module
    s = state.load(run)
    cat = checkins.load(playbook=s.playbook)
    ctx = Context(run, None, lang)
    decided = {cid: d for cid, d in _latest_decisions(run).items() if cid in cat.checkins}
    stages = []
    for n, (_, cid, d) in enumerate(sorted((d.get("at") or "", cid, d) for cid, d in decided.items()), 1):
        stages.append({"key": cid, "n": n, "name": name(ctx, cid), "title": "", "lede": "",
                       "blocks": materials(ctx, cid), "record": _record(None, d, outcome(ctx, cid, d.get("choice")))})
    stages.reverse()
    wanted = PAGE_STAGES if "briefs" in (s.outputs or []) else PAGE_STAGES[:1]
    key = next((cid for cid in wanted if cid not in decided), None)
    stage = None
    if key is not None and s.level and cat.route(key, s.level) != "rule":
        card = cat.checkins[key].card
        label = (_w(CARDS[card], lang) if card in CARDS else cat.cards[card].name) \
            if card and cat.route(key, s.level) == "card" else name(ctx, key)
        stage = {"key": key, "n": len(stages) + 1, "name": label}
    return {"stage": stage, "settled": template._settled(stages, ctx.ds, lang), "run": run.path.name,
            "updated": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")}
