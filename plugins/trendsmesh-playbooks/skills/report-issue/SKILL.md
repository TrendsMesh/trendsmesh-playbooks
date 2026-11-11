---
name: report-issue
description: Use when the user wants to report a problem, bug or error with the TrendsMesh playbooks, or ask for a feature or a change to how they work; also when a run failed and the user wants it looked at.
---

# Report an issue

Writes up a bug or a wish for a change, removes the user's private data, shows them the exact
text and where it goes, and files it only after their explicit yes: as a public GitHub issue under
their own name, or privately to the TrendsMesh team.

**The engine `tm` checks and sends; you write.** Call it as `tm ...` (the plugin puts it on PATH).
`tm report check` finds private data left in the draft; `tm report github` and `tm report send`
refuse a draft that is not clean (`not_clean`). Never call `gh issue create` or the inbox
yourself, never work around a refusal.

**Words:** talk to the user in their language, in plain words: they never see `tm`, a flag or
JSON. The report itself is always in **English**, whatever language the user writes in: say so
when you show it.

**Suggesting it:** after a failed run, or when the user is unhappy with the plugin, you may offer
to report it, **once a session** at most. Never file anything on your own.

**Acceptance reports are never filed here.** When the user asks to post, file or send an
acceptance report (a `report_vNN.md` in an `acceptance/` folder, or the results of
`/trendsmesh-playbooks:acceptance`), don't file it publicly and don't send it with this skill:
it holds their own numbers (their ads' results, their channel, their spend). Say so, and point
them to `/trendsmesh-playbooks:acceptance`'s way: they keep the file, or send it themselves,
privately, by email to contact@trendsmesh.com. A bug they hit during the acceptance can still be
reported here as its own report, written without the acceptance report's contents.

## The flow

1. **Kind.** `bug` (something broke or gave a wrong result) or `change` (a feature, or a change
   to how something works). Ask only when you can't tell, in one plain question.

2. **Draft.** Fill the bug or change template from `references/templates.md`, in English, from
   what the user said and what you can read (the run's files, the error, the log; the plugin
   version is `tm --version`; the OS and the Claude app if you can tell, otherwise "not known":
   don't ask for them). Write the body to `<workspace>/trendsmesh-report-<YYYY-MM-DD-HHMM>.md`
   (the folder you work in, the current date and time). The title is separate: short, specific,
   and free of private data too (`tm report github` and `tm report send` check it as well).

3. **Remove private data.** First your own rewrite, with neutral placeholders:
   - ad account, page, client and brand names → `<ad account>`, `<page>`, `<client>`, `<brand>`;
   - account, ad and campaign ids → `<account id>`; emails → `<email>`; tokens and keys → `<key>`;
   - money, spend, revenue and audience figures → `<amount>`;
   - the user's name and home folder in paths → `~/…`;
   - links with private paths or query strings → `<link>`;
   - quoted ad copy or customer words → `<ad text>`.

   Then `tm report check <file>`. It prints `clean` (exit 0), or one finding a line,
   `line<TAB>kind<TAB>value` (exit 1): replace each with its placeholder, and run the check again,
   **until it prints `clean`**. Exit 2: the file can't be read; fix the path.

4. **Find where it goes**, before you show it: `gh auth status --hostname github.com`.
   - Exit 0: **public, under your GitHub name** (an issue in TrendsMesh/trendsmesh-playbooks
     that anyone can read).
   - Anything else (no `gh`, or not signed in): **private, to TrendsMesh**. Never suggest
     installing `gh`, signing in to GitHub or creating an account: the private way is just as good.

5. **Show** the exact final title and body, as they will be sent, and name the destination in
   those words. Say what kinds of data you replaced (an account id, the brand, an amount), never
   the values themselves. Ask whether to send it.

6. **Wait for the explicit yes.** Nothing is sent before it. Any edit the user asks for goes into
   the file, through `tm report check` again, and is shown again before you ask again. A yes to
   the public issue covers the private inbox too (it shows less); a yes to private never covers
   public.

7. **Send.**
   - Public: `tm report github <file> --kind bug|change --title "<title>"`.
   - Private: `tm report send <file> --kind bug|change --title "<title>"`, with
     `--contact <email>` only when the user typed an email for a reply in this conversation.
   - **The user says no to public**: offer the private inbox instead, same text. When their
     answer already asks for private ("not public, send it to TrendsMesh"), that is the yes:
     send it. Otherwise ask, and wait.

   Each prints one JSON line; act on `outcome`:

   | Outcome | What to do |
   |---|---|
   | `filed` | Done: give the issue's link (`url`). |
   | `no_gh` | `gh` is gone or signed out: send it privately (`tm report send`), and say so. |
   | `failed` | GitHub refused (`reason`): say it in plain words, then send it privately. |
   | `received` | Done: give the `reportId`. |
   | `invalid` | One field was refused (`field`): fix that field once, check again, send again. |
   | `too_large` | Shorten once (the log lines first), check again, send again. |
   | `rate_limited` | Say when to try again (`retryAfter` seconds, in minutes), or use email now. |
   | `unavailable` | The inbox can't be reached (`reason`): email, below. |
   | `not_clean` | Replace the `findings`, check again, show the text again and ask again. |

   A second `invalid` or `too_large` after the fix goes to email too. A fix that only shortens
   the text or the title keeps the yes (tell the user what you cut); any other change is shown
   again and asked again.

   **Email**, the last way: the report is already saved. Give its full path, the address
   **contact@trendsmesh.com** and the title as the subject, and ask the user to send the file
   (attached, or its text pasted) themselves. Never write a `mailto:` link: it is unreliable
   inside apps, and the text can be cut. Never send the email yourself.

8. **Tell the user the outcome**, in plain words:
   - **Filed on GitHub**: the link; it is public under their name, and they can follow or add to
     it there.
   - **Sent privately**: the report id; the TrendsMesh team reads every report and publishes it
     after checking, so it isn't public yet. If they gave an email, the team can answer there.
   - **Email**: nothing was sent yet; the file's path, the address and the subject.

## Never

- suggest a report unasked more than once a session;
- file or send anything without the user's explicit yes to the exact text and destination;
- put account data in a public issue (ids, names, brands, amounts, emails, keys, home folders);
- send an acceptance report through this skill (point to `/trendsmesh-playbooks:acceptance`);
- write a `mailto:` link;
- ask the user to create a GitHub account, sign in to GitHub, or give a GitHub login.
