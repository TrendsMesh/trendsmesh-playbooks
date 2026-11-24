# When Claude Code refuses a step: allow once at readiness; on a refusal stop and give the rules (shared: every playbook)

Claude Code's permissions can refuse a step the user already approved in chat: in auto mode its classifier
blocks a call it reads as risky, and a deny rule blocks it in any mode. The result then says so, for example
"Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Destructive or Unwanted
Actions]", or that a rule denied it. So that a run doesn't stop again and again on the way, the plugin's commands
and pages are allowed once, before the run (section 1), with these three rules:

| Rule | What it allows |
|---|---|
| `Bash(tm *)` | every `tm` command run through the Bash tool |
| `PowerShell(tm *)` | the same through the PowerShell tool (Windows): a Bash rule does not cover it |
| `Artifact` | publishing the run's pages |

These are **the plugin's rules**: they cover every step below. A user who would rather allow less can add only the
narrow rule of each step instead (with `PowerShell` in place of `Bash` for the PowerShell tool, for example
`PowerShell(tm decide *)`):

| Step | Narrow rule |
|---|---|
| a decision (`tm decide`) | `Bash(tm decide *)` |
| an organic pick (`tm organic pick`) | `Bash(tm organic pick *)` |
| a spending approval (`tm budget approve`) | `Bash(tm budget approve *)` |
| a paid generation (`tm tool replicate_run`) | `Bash(tm tool replicate_run *)` |
| a voice or music call (`tm tool elevenlabs`) | `Bash(tm tool elevenlabs *)` |
| going on after a stop (`tm resume`) | `Bash(tm resume *)` |
| a brief's concept choice and its wait (`tm brief choose`, `tm brief await`) | `Bash(tm brief choose *)`, `Bash(tm brief await *)` |
| a page's wait, publish record and intake (`tm page await`, `tm page published`, `tm page intake`) | `Bash(tm page await *)`, `Bash(tm page published *)`, `Bash(tm page intake *)` |
| a page publish (`Artifact`) | `Artifact` |
| a report (`tm report github`, `tm report send`) | `Bash(tm report *)` |

**One `tm` command per call.** A rule matches the command as it is written, and Claude Code splits a command at
`&&`, `||`, `;`, `|`, `&` and line breaks, every part needing a rule of its own: a compound `cd … && tm …` or
`…; tm …` never matches a rule. So:

- Run each step as a command of its own that starts with `tm`: no `cd ... &&` in front, no full path to `tm`, no
  pipe after it.
- Keep it on one line. Words with quotes or line breaks of their own go in a file: `tm decide ... --said-file
  <path>` (UTF-8), not `--said "..."` across lines.

A rule that seemed to work once and fail later usually met a command written another way (a `cd` in front, a line
break inside the user's words, the PowerShell tool), not a choice the rule disliked: the rule never reads the
answer.

## 1. Allow once, at readiness (before the run)

At readiness, before the run's first step, run

```
tm permissions allow --json
```

(a dry run: it writes nothing). It says which of the three rules the folder already has (in the folder's
`.claude/settings.local.json` or `.claude/settings.json`, or the user's `~/.claude/settings.json`), Claude Code's
permission mode for this session (`mode`, read by the plugin's hook; `unknown` when it could not be read), the rules
this system needs (`needed`), and `ask`. Only a rule the system needs counts: on a Mac or Linux that is `Bash(tm *)`
and `Artifact`, so a missing `PowerShell(tm *)` alone asks nothing; on Windows, where Claude Code may run `tm`
through its Bash tool or its PowerShell tool, all three count.

- `ask` false (every rule this system needs is there, or the session is not in auto mode): say nothing about
  permissions.
- `ask` true (auto mode, or a mode that could not be read, and a rule this system needs is missing): ask once, in
  the user's language, in the words of its `question`: "So the run doesn't stop on the way, allow the plugin's
  commands and its pages?" Add in one line that it goes into `.claude/settings.local.json` in this folder (only
  them, only this folder) and that they can take it out there at any time. Ask it together with readiness's other
  questions, never as a stop of its own.
  - **Yes**: `tm permissions allow --yes --json`. It adds every missing rule of the three (on a Mac or Linux
    `PowerShell(tm *)` too, when it is missing) to `permissions.allow` in that file, after the user's own rules,
    keeping everything else in it as it is (it makes the file when there is none); Claude Code reads the change
    without a restart. Say in one line what was added.
  - **No**, or no answer: go on. A later refusal is handled as in section 2, with the same rules.
  - It refuses a file that is not valid JSON (exit 1, nothing written): give the user its message (the file, and
    the rules to add by hand), and go on.

Only after the user's explicit yes, never on your own, and never for any other rule or file: `tm permissions allow
--yes` is the one way the plugin writes a settings file. Never edit their settings files yourself in any other way,
and never suggest turning permissions off.

## 2. A refusal is a stop, never a fallback

1. **Stop there.** Never run the same step again with other words, another flag order, a wrapper or another tool,
   and never go on to the next step as if it had run. A refused publish is not "no publishing tool": never switch
   to a local page on your own (`pages.md`, "Without a publishing tool", is only for a session that has no
   publishing tool at all).
2. **Record it** in the run, when there is one:
   `tm stop --run R --reason permission_denied --what "<the step> was blocked by Claude Code's permissions
   (<the reason in brackets>); nothing was saved, spent or published" --todo "allow the plugin's commands and
   pages: Bash(tm *), PowerShell(tm *) and Artifact in permissions.allow"`.
   A refused page publish at readiness, before any run, is `artifacts=denied` for the doctor instead.
3. **Tell the user, in one message:** which step was blocked; the reason Claude Code gave, in its brackets; that
   nothing was saved, spent or published; and the way to allow it, **the whole set at once, never one rule at a
   time**:
   - ask the question of section 1 ("So the run doesn't stop on the way, allow the plugin's commands and its
     pages?"); on their yes, `tm permissions allow --yes --json`;
   - or they add the three rules themselves to `permissions.allow` in `.claude/settings.local.json` in the folder
     they work in (only them; `.claude/settings.json` there is shared with everyone who opens the folder, and
     `~/.claude/settings.json` covers every folder):
     `{"permissions": {"allow": ["Bash(tm *)", "PowerShell(tm *)", "Artifact"]}}`; Claude Code reads the change
     without a restart;
   - or they approve that one step when Claude Code asks (outside auto mode it asks before each such step).
   When `tm permissions allow --yes` is itself refused, give the second way (the rules to add by hand), once.
4. **On their "done"** (or once the rules are added): `tm resume --run R`, then run the same command once more,
   exactly as before. Refused again: stop again the same way, once, and wait.

**A page publish refused for "Sensitive Information Leakage"** (or another reason about what the page holds) is a
judgement of Claude Code's classifier on the page, which the plugin can't prevent. Handle it as above: stop, say so,
and ask the same allow question (the `Artifact` rule is in the set); on their "done", publish the same page again.
