# Template: diagnosis report (`04_final/diagnosis_report_vNN.md`)

Filled by the engine when "Accept the diagnosis" (G1a) is recorded as `do_not_refresh`, by the user or by rule
(`tm.diagnosis_report`), never by hand: everything below the line is the report, with `$name` placeholders (Python
`string.Template`) the engine fills from run.json, the ranking (`01_base/winner_ranking_vNN.json`), the diagnosis
windows (`03_wip/diagnosis_windows/`) and the diagnosis (`04_final/diagnosis_vNN.json`: the ad it judged, the two
windows it was judged on, and the structural check). Every figure is Meta's, as the run read it. The words are the
string table's `diagnosis.*` area, in the run's working language (`languages.working`); when that language's table
lacks some of them, the report is in English and `tm decide` says so (`warning`): then tell the user what it says
in their language.

---

# $title

$written

## $heading_checked

$checked

## $heading_shows

$shows

## $heading_fix

$fix

## $heading_spent

$spent
