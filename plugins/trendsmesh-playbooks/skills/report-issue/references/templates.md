# Report templates

The body of the report, saved as `trendsmesh-report-<YYYY-MM-DD-HHMM>.md` in the workspace. Always
in English. The title is not in the file: it goes with `--title`. Keep what is known, write "not
known" for what isn't, and leave out a section only when it has nothing to say. Placeholders for
private data are in `SKILL.md`, step 3.

## Title

One line, under 80 characters, saying what is wrong or what is wanted, specifically and without
private data. For example: "Refresh an ad stops with KeyError 'frequency' on an ad without
frequency", "Weekly trend digest as a CSV file".

## Bug

```markdown
## What happened

<One to three sentences: what the user asked for, and what went wrong. Quote the error message
exactly, with private data replaced.>

## What I expected

<One or two sentences.>

## Steps to reproduce

1. <The playbook or command, and the step it was at.>
2. <...>

## Setup

- Plugin version: <from `tm --version`, for example 0.9.2>
- OS: <macOS, Windows or Linux, with its version if known>
- Claude app: <Claude Code in a terminal | the Claude desktop app | Cowork | not known>

## Log

<The relevant lines only, shortened: the error and the few lines before it, at most about 20.
Paths start at `~/`.>

    <log lines>
```

## Change

```markdown
## The problem

<What the user is trying to do, and what gets in the way today.>

## What I'd like

<The feature or the change, in one to three sentences.>

## Why

<What it would let them do, or how often they hit this.>

## Setup

- Plugin version: <from `tm --version`>
```
