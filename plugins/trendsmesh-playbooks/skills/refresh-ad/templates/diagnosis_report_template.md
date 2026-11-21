# Template: diagnosis report (`04_final/diagnosis_report_vNN.md`)

Filled by the engine when "Accept the diagnosis" (G1a) is recorded as `do_not_refresh`, by the user or by rule
(`tm.diagnosis_report`), never by hand: everything below the line is the report, with `$name` placeholders (Python
`string.Template`) the engine fills from run.json, the ranking (`01_base/winner_ranking_vNN.json`), the diagnosis
windows (`03_wip/diagnosis_windows/`) and the diagnosis (`04_final/diagnosis_vNN.json`, with the structural check).
Every figure is Meta's, as the run read it. It is written in English; tell the user what it says in their language.

---

# Diagnosis report: $ad

Written $written. The run ended at the diagnosis, so no change was made to the ad.

## What was checked

$checked

## What the data shows

$shows

## What to fix

$fix

## What was spent

$spent
