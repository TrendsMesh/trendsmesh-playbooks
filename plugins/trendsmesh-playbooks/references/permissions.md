# When Claude Code refuses a step: stop, say why, give the allow rule (shared: every playbook)

Claude Code's permissions can refuse a step the user already approved in chat: in auto mode its classifier
blocks a call it reads as risky, and a deny rule blocks it in any mode. The result then says so, for example
"Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Destructive or Unwanted
Actions]", or that a rule denied it. This holds for any call, most often these:

| Step | Rule to add to `permissions.allow` |
|---|---|
| a decision (`tm decide`) | `Bash(tm decide *)` |
| an organic pick (`tm organic pick`) | `Bash(tm organic pick *)` |
| a spending approval (`tm budget approve`) | `Bash(tm budget approve *)` |
| a paid generation (`tm tool replicate_run`) | `Bash(tm tool replicate_run *)` |
| a voice or music call (`tm tool elevenlabs`) | `Bash(tm tool elevenlabs *)` |
| a page publish (`Artifact`) | `Artifact` |
| a report (`tm report github`, `tm report send`) | `Bash(tm report *)` |

When the command ran through the PowerShell tool (Windows), the rule is the same with `PowerShell` in place of
`Bash`, for example `PowerShell(tm decide *)`: a Bash rule does not cover the PowerShell tool.

## A refusal is a stop, never a fallback

1. **Stop there.** Never run the same step again with other words, another flag order, a wrapper or another tool,
   and never go on to the next step as if it had run. A refused publish is not "no publishing tool": never switch
   to a local page on your own (`pages.md`, "Without a publishing tool", is only for a session that has no
   publishing tool at all).
2. **Record it** in the run, when there is one:
   `tm stop --run R --reason permission_denied --what "<the step> was blocked by Claude Code's permissions
   (<the reason in brackets>); nothing was saved, spent or published" --todo "<the rule from the table>"`.
   A refused page publish at readiness, before any run, is `artifacts=denied` for the doctor instead.
3. **Tell the user, in one message:** which step was blocked; the reason Claude Code gave, in its brackets; that
   nothing was saved, spent or published; and the way to allow it:
   - add the rule from the table to `permissions.allow` in `.claude/settings.local.json` in the folder they work
     in (only them; `.claude/settings.json` there is shared with everyone who opens the folder, and
     `~/.claude/settings.json` covers every folder), for example
     `{"permissions": {"allow": ["Bash(tm decide *)"]}}`; Claude Code reads the change without a restart;
   - or approve that one step when Claude Code asks (outside auto mode it asks before each such step).
   Never edit their settings files yourself, and never suggest turning permissions off.
4. **On their "done":** `tm resume --run R`, then run the same command once more, exactly as before. Refused
   again: stop again the same way, once, and wait.

## Commands an allow rule can match

A rule matches the command as it is written. Claude Code splits a command at `&&`, `||`, `;`, `|`, `&` and line
breaks, and every part needs a rule of its own, so:

- Run each of these steps as a command of its own that starts with `tm`: no `cd ... &&` in front, no full path to
  `tm`, no pipe after it.
- Keep it on one line. Words with quotes or line breaks of their own go in a file: `tm decide ... --said-file
  <path>` (UTF-8), not `--said "..."` across lines.

A rule that seemed to work once and fail later usually met a command written another way (a `cd` in front, a line
break inside the user's words, the PowerShell tool), not a choice the rule disliked: the rule never reads the
answer.
