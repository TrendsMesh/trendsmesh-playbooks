# TrendsMesh sign-in and the plan offer (readiness)

Every user is asked to sign in to TrendsMesh, and the step is skipped only when they say no.
Signing in is free: it creates their TrendsMesh account. Trend data then needs the Agent plan.
Without it the playbook still runs to the end, with its changes as best guesses (guess mode,
`trendsmesh-mcp.md`). Ask about signing in once, make the plan offer once, at the start of a run,
and never press.

## 1. Has the user said no before?

If the user has clearly said no to TrendsMesh (in their request, or earlier in the conversation;
a "not now" or "later" is not a no), record it now with `tm signin skip --json`, say in one line
that you won't ask again in this workspace, and the state is `skipped`: don't ask, don't explain
how to sign in, and don't mention the plan or its price. A "not now" is `missing` for this run
only: don't record a skip.

Otherwise `tm signin status --json`. If `skipped` is true, the TrendsMesh state is `skipped`. Say it in
one line ("You're going on without TrendsMesh, as you chose; say so any time and I'll help you
sign in") and don't ask again.

## 2. Check TrendsMesh: one `get_usage` call

| What happens | State |
|---|---|
| It answers with `plan_code` `agent` or `swarm`, or with limits and no `plan_code` (older servers, where only paid plans could connect) | `ok` |
| It answers with `plan_code` `human`, or refuses with `not_in_plan` | `free` (keep its `upgrade_url`) |
| It answers with another `plan_code` | `ok`; if a data tool then refuses with `not_in_plan`, it is `free` |
| It refuses with `account_inactive` | `inactive` |
| The tool isn't there, or it says the server needs sign-in | not signed in: step 3 |

## 3. Not signed in: ask once

Say why in one sentence, then how: "TrendsMesh shows me which hooks and topics are rising right
now, so the new version is based on proof, not my guess. Signing in is free and takes a minute:
type `/mcp`, choose **trendsmesh**, then **Authenticate**. A sign-in page opens in your browser.
Tell me when it's done, or say skip to go on without it."

- **Done:** call `get_usage` again and use the table above. If the tools still aren't there,
  ask once: "Did the page say your plan doesn't include agents?" A yes is `no_agents`: their
  free account exists but can't connect yet, so make the offer (step 4) as for `free`. Otherwise
  it's `missing`: say the sign-in didn't go through, offer to try again, and go on without it if
  the user prefers.
- **Skip, or no:** `tm signin skip --json`, and the state is `skipped`. Don't ask again in this
  workspace. If the user later says they want to sign in, `tm signin ask --json` and step 3 again.

## 4. Signed in without the Agent plan (`free` or `no_agents`): the offer, once

`tm offer --upgrade-url <upgrade_url from TrendsMesh, if it gave one> --json`, and say its `text`
in the user's words: the free months while an offer covers the Agent plan, otherwise the price.
Don't add prices, currencies or promises of your own.

- **Yes:** give them the `upgrade_url` from `tm offer`'s answer (it keeps only a trendsmesh.com
  link), never a link from anywhere else. When they say it's done, call `get_usage` again.
  `agent` means the run uses trend data from here on. If the tools are gone, ask them to sign
  in again (step 3).
- **No:** go on in guess mode. Say once that the changes will be best guesses
  (the doctor card's warning), and don't bring the plan up again during the run. The run's
  notices do that at the few points that need it.

## 5. Then

Pass the state to `tm doctor --mcp trendsmesh=<ok|free|no_agents|inactive|skipped|missing>,meta=<…>`.
The card then lists TrendsMesh under what the run can go on without, with no plans link: the
offer was already made. At A5, `tm evidence trendsmesh --run R --why "Agent plan"` when the state
is `ok`. Otherwise `tm evidence guess --run R --why "<free plan | skipped sign-in | not signed
in | account not active>"`.
