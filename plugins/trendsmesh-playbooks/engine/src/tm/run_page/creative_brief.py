"""Creative brief on the shared run page (issue #60): its stage materials and outcomes (`COMPONENTS`, `OUTCOMES`),
its check-ins' names (`run_page.creative_brief.stage.<id>`), and the frame `tm brief page` puts around the brief (`frame`).

    materials(ctx, checkin)          a settled check-in's materials: the concepts kept and dropped (G3; a run started
                                     before issue #145: G2), and the team's decisions as read from the page (G3, G4:
                                     each concept's verdict, every note whole)
    outcome(ctx, checkin, choice)    the decision in words ("C1, C3 kept", "Accepted")
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

PAGE_STAGES = ("G3", "G4")                       # check-ins decided on the brief's page (tm.brief_page.STAGES)
RUN_PAGE_STAGES = ("G0", "G1")                   # decided on the run page before the brief's (issue #131): the
                                                 # same link; `tm page build --ask` at A1 and B1
CHOSEN_AT = ("G3", "G2")                         # where the choice is shown; G2: a run started before issue #145
REVIEW_STAGE = "C1"                              # the review pack alone: decided on C1's page, no check-in
LEGACY = ("G2",)                                 # check-ins before issue #145: still shown settled in an old run
DECIDING = ("decision", "strategy", "media-buyer")  # the views that decide; the creator's shows no decision
SETTLED_VIEWS = ("decision", "strategy")         # the views that see the settled check-ins (G1's account data)
CARDS = {"approve_setup": "brief.card_approve_setup", "approve_briefs": "brief.card_approve_briefs"}
VERDICTS = {"approved": "brief.verdict_approved", "changes": "brief.verdict_changes",
            "dropped": "brief.verdict_dropped", "split": "brief.verdict_split", "none": "brief.verdict_none"}
CHOSEN = {"page": "brief.chosen_page", "chat": "brief.chosen_chat", "rule": "brief.chosen_rule"}
CHOICES = {"approve": "brief.approved", "change": "brief.changes_requested", "drop": "brief.dropped"}


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
    concepts = _chosen(ctx.run).get("concepts") if checkin in CHOSEN_AT else None
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


def _intake(ctx: Context) -> list[dict]:
    """G0, the intake card (issue #131): what the run was set up with, from its config."""
    from tm import config
    try:
        cfg = config.load(ctx.run)
    except (OSError, ValueError):
        return []
    product = cfg.get("product") if isinstance(cfg.get("product"), dict) else {}
    langs = cfg.get("languages") if isinstance(cfg.get("languages"), dict) else {}
    brief = cfg.get("brief") if isinstance(cfg.get("brief"), dict) else {}
    account = cfg.get("account") if isinstance(cfg.get("account"), dict) else {}
    s = state.load(ctx.run)
    rows = [(_w("brief.intake_product", ctx.lang), product.get("name")),
            (_w("brief.intake_landing", ctx.lang), product.get("landing_url")),
            (_w("brief.intake_category", ctx.lang), product.get("category_phrase")),
            (_w("brief.intake_market", ctx.lang), account.get("market") or cfg.get("market")),
            (_w("brief.intake_languages", ctx.lang), " / ".join(str(x) for x in (langs.get("working"),
                                                                                  langs.get("market")) if x)),
            (_w("brief.intake_concepts", ctx.lang), (cfg.get("concepts") or {}).get("count")
             if isinstance(cfg.get("concepts"), dict) else None),
            (_w("brief.intake_recipients", ctx.lang), len(brief.get("recipients") or []) or None),
            (_w("brief.intake_level", ctx.lang), ctx.t_or(f"level.{s.level}", s.level) if s.level else None)]
    rows = [(k, v) for k, v in rows if v not in (None, "", [])]
    return [{"kind": "facts", "rows": rows, "source": config.FILE}] if rows else []


def _persona(ctx: Context) -> list[dict]:
    """G1, the persona (issue #131): the hypothesis next to the age × gender results and the placements (as Refresh
    an ad's audience stage shows them), and the account context with the winners, the losers and the divergence. On
    the brief's page this is in the deciding views only (the creator's never shows the account's figures)."""
    from tm.run_page import refresh_ad
    out = refresh_ad._audience(ctx)
    path = ctx.inside("01_base/account_context.md")
    text = ctx.text(path) if path else None
    if text:
        out.append({"kind": "text", "title": _w("brief.account_context", ctx.lang), "text": text, "pre": True,
                    "summary": _w("brief.account_context_open", ctx.lang), "source": "01_base/account_context.md"})
    return out


def materials(ctx: Context, checkin: str) -> list[dict]:
    if checkin == "G0":
        return _intake(ctx)
    if checkin == "G1":
        return _persona(ctx)
    lang, out = ctx.lang, []
    chosen = _chosen(ctx.run) if checkin in CHOSEN_AT else {}
    if chosen.get("concepts"):
        source = CHOSEN.get(chosen.get("source"))
        out.append({"kind": "text", "text": _w("brief.settled_chosen", lang,
                                               concepts=", ".join(map(str, chosen["concepts"])),
                                               source=_w(source, lang) if source else str(chosen.get("source") or ""))})
        if chosen.get("dropped"):
            out.append({"kind": "text", "text": _w("brief.settled_dropped", lang,
                                                   concepts=", ".join(map(str, chosen["dropped"])))})
    found = _read(ctx.run, checkin) if checkin in (*PAGE_STAGES, "G2") else None
    if found is None:
        return out
    rel, data = found
    verdicts = data.get("verdicts") if isinstance(data.get("verdicts"), dict) else {}
    lines = []
    for cid, v in verdicts.items():
        key = VERDICTS.get(v.get("verdict")) if isinstance(v, dict) else None
        if key:
            lines.append(_w(key, lang, id=cid, approve=v.get("approve") or 0, change=len(v.get("change") or []),
                            drop=v.get("drop") or 0))
    for cid in verdicts:                      # every note whole (issue #55), by concept, then person
        for d in data.get("docs") or []:
            x = ((d.get("decisions") or {}).get(cid) if isinstance(d, dict) else None) or {}
            note = x.get("n") if isinstance(x, dict) else None
            if x.get("d") in CHOICES and isinstance(note, str) and note.strip():
                lines.append(_w("brief.settled_note", lang, id=cid, who=d.get("who"), choice=_w(CHOICES[x["d"]], lang),
                                note=note))
    out.append({"kind": "text", "text": _w("brief.settled_read", lang), "source": rel})   # the file: Technical details
    if lines:
        out.append({"kind": "list", "items": lines})
    return out


def frame(run, lang: str) -> dict:
    """What `tm brief page` puts around the brief: `{stage, settled, updated, run}`. `stage` is the check-in the page
    is up for (`{key, n, name}`, its card's name at Just the big calls), None when none is decided on the page now
    (all are settled, or Hands-off decides by rule; the review pack alone is up for its concepts, `C1`, until the
    choice is recorded); `settled` is the "Already settled" group's HTML (newest first), empty when nothing is
    decided yet."""
    from tm.run_page import _latest_decisions, _record     # the run page builds its page with this module
    s = state.load(run)
    cat = checkins.load(playbook=s.playbook)
    ctx = Context(run, None, lang)
    decided = {cid: d for cid, d in _latest_decisions(run).items() if cid in cat.checkins or cid in LEGACY}
    stages = []
    for n, (_, cid, d) in enumerate(sorted((d.get("at") or "", cid, d) for cid, d in decided.items()), 1):
        stages.append({"key": cid, "n": n, "name": name(ctx, cid), "title": "", "lede": "",
                       "blocks": materials(ctx, cid),
                       "record": _record(None, d, outcome(ctx, cid, d.get("choice")), lang=lang,
                                         fixed=cat.checkins[cid].choices if cid in cat.checkins else None)})
    stages.reverse()
    stage = None
    if "briefs" not in (s.outputs or []):                  # the review pack alone: no check-in, C1's page decides
        if s.level and s.level != "hands_off" and not _chosen(run).get("concepts"):
            stage = {"key": REVIEW_STAGE, "n": len(stages) + 1, "name": name(ctx, REVIEW_STAGE)}
        return {"stage": stage, "settled": template._settled(stages, ctx.ds, lang), "run": run.path.name,
                "updated": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")}
    key = next((cid for cid in PAGE_STAGES if cid not in decided), None)
    if key is not None and s.level and cat.route(key, s.level) != "rule":
        card = cat.checkins[key].card
        label = (_w(CARDS[card], lang) if card in CARDS else cat.cards[card].name) \
            if card and cat.route(key, s.level) == "card" else name(ctx, key)
        stage = {"key": key, "n": len(stages) + 1, "name": label}
    return {"stage": stage, "settled": template._settled(stages, ctx.ds, lang), "run": run.path.name,
            "updated": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")}
