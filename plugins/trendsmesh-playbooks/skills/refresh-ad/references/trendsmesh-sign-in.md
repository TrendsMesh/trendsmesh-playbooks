# TrendsMesh readiness: Free or Paid

The user chooses how the playbook finds trends:

- **Paid: TrendsMesh.** The run reads TrendsMesh's always-on, real-time trend analysis: the hooks, topics,
  sounds and formats that repeat across many creators over time, each with evidence and a lifecycle stage.
  Signing in is free; trend data needs the Agent plan.
- **Free: the AI guesses.** No TrendsMesh. You work from what you can see alone (trending tabs and public
  trend lists, the Meta Ad Library, the user's own channel and ads, web search, your own knowledge), and
  every trend claim is labelled a guess.

Free is the user's decision, never a fallback. Nothing runs on guesses until the user says Free: the engine
refuses `tm evidence guess` without that choice. **A clear "no" to TrendsMesh is the user saying Free** ("I don't
want TrendsMesh", "no sign-ups", "leave it out"): record it at once (`tm mode free --json`) and go on, without
asking them to confirm it. What you never do is choose Free for them when they said nothing. Trend research is
Paid only (section 7).

## 1. What has the user chosen?

From the workspace, `tm mode status --json`:

- **`mode` free.** Open the run with one line: "You're on Free, with the AI guessing, as you chose. For this
  <run>, TrendsMesh would show <what it adds to this run, from the table in section 4>. Say 'connect
  TrendsMesh' any time." Don't ask the question again. If the TrendsMesh tools are in this session (signed
  in), one `get_usage` call: when it answers with trend data (`ok`, section 2), say in one line that this run
  uses TrendsMesh, `tm mode paid --json`, and go on as Paid. Otherwise don't call TrendsMesh at all. When
  `offer_due` is true, add the plan offer once, after that line (section 5): one sentence, never pressed,
  and never when the user asked not to hear about plans.
- **`mode` paid.** Check TrendsMesh (section 2). Ready: go on. Not ready: ask the question (section 4); a
  lapsed plan never drops to Free on its own.
- **No choice (`mode` null).** If the user's request already says they don't want TrendsMesh ("without
  TrendsMesh", "no sign-ups"), that is Free, chosen: `tm mode free --json` before the doctor, say in one line
  that it is remembered for this workspace and that they can say "connect TrendsMesh" any time, and go on.
  Don't ask them to confirm it, don't ask them to sign in, and don't make the offer in that run. A "not now" or "later" is
  not a choice: ask the question (section 4). Otherwise check TrendsMesh
  (section 2): ready is Paid (`tm mode paid --json`); not ready, ask the question (section 4).
  `legacy_skip` true means the user skipped the sign-in in an earlier version: that was not a choice of
  Free, so ask the question once.

## 2. Check TrendsMesh: one `get_usage` call

| What happens | State |
|---|---|
| It answers with `plan_code` `agent` or `swarm`, or with limits and no `plan_code` (older servers, where only paid plans could connect) | `ok` |
| It answers with `plan_code` `human`, or refuses with `not_in_plan` | `free` (keep its `upgrade_url`) |
| It answers with another `plan_code` | `ok`; if a data tool then refuses with `not_in_plan`, it is `free` |
| It refuses with `account_inactive` | `inactive` |
| The tool isn't there, or it says the server needs sign-in | `missing` (not signed in) |

## 3. Paid, not signed in: the sign-in

"Signing in is free and takes a minute: type `/mcp`, choose **trendsmesh**, then **Authenticate**. A sign-in
page opens in your browser. Tell me when it's done."

- **Done:** `get_usage` again and use the table. If the tools still aren't there, ask once: "Did the page say
  your plan doesn't include agents?" A yes is `no_agents`: their account exists but can't connect yet, so
  make the offer (section 5). Otherwise the sign-in didn't go through: offer to try again, or ask the question
  (section 4) again.

## 4. TrendsMesh isn't ready: one question, Free or Paid

Ask one question with two answers, at every level (Hands-off too: it is asked like the launch). A run with
nobody there to answer (a scheduled run) stops and leaves the question; it never chooses.

- **Paid:** connect TrendsMesh: the sign-in (section 3), or, when they are signed in without the Agent plan,
  the plan offer itself (`tm offer`, section 5), said inside this answer so the question is asked once.
- **Free:** go on with you guessing, with one line on what that means for this playbook (the doctor's Free
  line says it).

The question carries one sentence on what Paid adds for this playbook:

| Playbook | What Paid adds |
|---|---|
| Refresh an ad | which hooks are repeating across creators right now, and how early, so the new version rides one that is still rising |
| Creative brief | concepts that each ride a hook or topic repeating across creators right now, with the videos as evidence |
| Create an ad | model ads and trends that are rising now: hooks, sounds and formats repeating across creators, with evidence |
| Organic AI video | ideas built on hooks, topics, sounds and formats repeating across creators right now, how early each is, and real videos to copy the structure from |

When the user asks why, the argument is: you alone see the surface (a trending tab shows what is already big,
as a list, and you start from zero each run); TrendsMesh watches creator videos all day, every day, keeps the
history, and sees a hook come back across creators over days while it is still early; every trend comes with
evidence and a lifecycle stage. Linking organic trends to ads is work in progress: never quote a lead time.

- **Free:** `tm mode free --json` (remembered for the workspace), then the one line. Say it as a statement and
  go on.
- **Paid:** sections 3 and 5. `tm mode paid --json` once TrendsMesh answers with trend data.

## 5. Signed in without the Agent plan (`free`, `no_agents`): the offer

`tm offer --upgrade-url <upgrade_url from TrendsMesh, if it gave one> --json`, and say its `text` in the
user's words: the free months while an offer covers the Agent plan, otherwise the price. Don't add prices,
currencies or promises of your own. `tm offer` notes when it was made: on Free it comes back at most once
every 30 days (`offer_due` in `tm mode status`).

- **Yes:** give them the `upgrade_url` from `tm offer`'s answer (it keeps only a trendsmesh.com link), never a
  link from anywhere else. When they say it's done, `get_usage` again: `agent` means the run uses trend data
  from here on (`tm mode paid --json`). If the tools are gone, ask them to sign in again (section 3).
- **No:** ask whether to go on with Free for this run. A yes is `tm mode free --run R --json` after `tm run
  new` (this run only: the next run asks again). If they say Free from now on, `tm mode free --json` instead.
  A no: the run waits until TrendsMesh is ready.

## 6. TrendsMesh stops mid-run (a Paid run)

A lapsed plan, an expired sign-in or a `not_in_plan` refusal: say what stopped, give the way back (the
`upgrade_url`, or the sign-in in section 3), and wait. Going on as guesses is the second option, only on the
user's yes: `tm mode free --run R --json`, then `tm evidence guess --run R --why "<what stopped>; the user
chose Free for this run"`. That switch is possible only until the list of changes is final (Refresh an ad
A7, Creative brief C1, Create an ad S3); after it, tell the user and write what you have (a trend status you
can't fetch is `unknown`). Organic AI video doesn't switch mid-run: it waits, or the user starts a new run on
Free. A rate limit: wait for the reset, from the same place.

## 7. Trend research is Paid only

It has no Free mode: its stages, its "act now" and "too late" calls and the weekly check of last week's
calls are TrendsMesh numbers. When TrendsMesh isn't ready, say in plain words why it needs TrendsMesh (it
reports what repeats across creators over time, which you can't see on your own), then the sign-in (section
3) or the offer (section 5), once. Never offer to run it on guesses.

## 8. Then: the doctor and the evidence

`tm doctor ... --mcp trendsmesh=<ok|free|no_agents|inactive|missing>,<the playbook's others>`. The doctor reads
the workspace's choice itself; for Free for this run only, add `--mode free`. On Free, leave `trendsmesh` out
of `--mcp` when you didn't call it: the card shows one line, "Free mode, your choice", with what Free misses.
Not chosen yet, a TrendsMesh row says the choice is the user's.

At the playbook's evidence step: `tm evidence trendsmesh --run R --why "Agent plan"` when TrendsMesh answers
with trend data; on Free, `tm evidence guess --run R --why "the user chose Free"`.
