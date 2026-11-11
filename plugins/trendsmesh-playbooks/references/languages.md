# Languages: the working language and the market language (shared: every playbook)

Nothing here is specific to one language: a run in Spanish, Italian, Polish or Japanese follows the same rules.

## Two languages per run

| | What it is for | Default |
|---|---|---|
| **Working language** | everything the user and their team read: check-in cards, pages and their labels and help, briefs, reports, summaries, the phrases offered to the user (the weekly run's) | the language the user writes to Claude in |
| **Market language** | everything the audience sees or hears: ad copy, captions, voiceover, on-screen text, cover text, post text | the working language, unless the account, the landing page, the channel profile or the user points to another market |

They can differ: an English-speaking agency working for a Spanish market (working `en`, market `es`), a team that
reads English while the ads are in Polish (working `en`, market `pl`).

**No extra question.** The intake's confirmation card shows both, filled from the defaults ("Working language:
Italian · Market language: Italian"), and the user corrects them in the same reply. Both go into config.yaml as
BCP 47 tags, under one key in every playbook:

```yaml
languages: {working: it, market: it}
```

Write the tags (`pl`, `es`, `pt-BR`), not names. `tm config check` names a value that is not a tag. A config written
before this key still works: refresh-ad's and creative brief's `account.language`, trend research's `language` and
`market_lang`, organic video's `page_lang` are read as the run's languages.

`tm` messages stay English: say them to the user in the working language.

## Pages in the working language

The engine builds every page (Creative brief, Trend research's report, digest and paid view, Organic AI video's pages, Refresh an ad's run page)
from one English table of its fixed words, `data/i18n/en.yaml`. For another working language the table is
translated once, by you, and kept in the plugin data folder for every later run in that language:

1. A page command that has no translation says so (`language_warning` in its JSON, a sentence in its text) and
   builds the page in English. Tell the user in one line, then translate:
2. `tm i18n export --lang <tag> --out i18n_<tag>.yaml` (in the run folder or the workspace) writes the strings
   still missing, in English.
3. Translate each value in that file into the working language, for the people who read the pages. Keep every
   `{placeholder}` and every `<tag>` exactly; never change a key.
4. `tm i18n import --lang <tag> i18n_<tag>.yaml` checks every key, placeholder and tag and keeps the translation
   (all or nothing: it names what to correct). Build the page again: it is in the working language, with its
   `lang` attribute.

`tm i18n check --lang <tag>` says what is still missing. When an English string changes in a later version, its
translation counts as missing again, so a page never mixes an old translation with new English silently. The table
also holds `checks.creator_words` (CB13, below) and `trends.weekly_phrase`; translate them like the rest.

The plugin ships Polish for Organic AI video's pages (`data/i18n/pl.yaml`); a translation you import wins over it.

## What the checks do in other languages

- **CB13** (Creative brief, nothing confidential in the creator view) looks for ad and research words in English
  and in the working and market languages' translated `checks.creator_words` (a comma-separated list; `word*`
  matches any ending, for languages that inflect). `tm brief check --stage production` says which languages it
  read and names any it could not: then read the creator view yourself, or translate the table and check again.
- **Glance rows** (Creative brief): the engine finds the trend, Account and Competition rows by their `key`
  (`trend`, `guess`, `customers`, `account`, `competition`), so a brief in another language labels them in that
  language and keys each row. A row without a key must carry the English label.
- **The shortlist** (`tm trends shortlist`) ranks languages against the run's market language unless
  `--market-language` is given.
- **File names** keep their letters: é → e, ß → ss, ł → l, ś → s. Letters of other scripts are kept as a short
  digest of the text.

## Customer voice in the market language (CB5)

Search the category's voice in the market language first (local forums, review sites, the brand's reviews), and
use another language's sources as a fallback marked as such. The language bank stays verbatim, in the language the
customers wrote. When a concept needs a bank phrase in the market language and the phrase is in another language,
translate it as plainly as the customer said it, and mark it in brief.json's `customer_phrases`:
`{"phrase": "<the translation>", "translated": true, "adapted_from": "<the bank phrase, as the bank has it>", ...}`.
The original stays the source (its link and item); a translated phrase is never presented as a customer's own
words in the market language.

## For engine code (`tm.i18n`)

Other modules switch their own English strings onto the table the same way:

- Add the strings under your area in `data/i18n/en.yaml` (`<area>.<key>`, nested in the file), English exactly as
  shown today, `{name}` placeholders, markup only when unavoidable.
- `i18n.run_languages(run)` → `Languages(working, market)` (tags; English when nothing is set);
  `i18n.languages_of(cfg)` the same from a config dict. Use these, never a config key directly.
- `pl = i18n.page_lang(languages.working, "<area>", ...)`: build in `pl.lang` (the working language when its
  table has every key of those areas, else English), put `pl.lang` in `<html lang>`, and surface `pl.warning`
  (not None when it fell back) in the command's text and as `language_warning` in its JSON.
- `tr = i18n.translator(pl.lang)`; `tr("<area>.<key>", **values)`. `i18n.t(key, lang, **values)` is the same for
  one string. Both raise `i18n.Missing` (a missing translation, never a silent English) and KeyError (a key the
  English table lacks).
- Escape a translated value for where it goes (HTML text, attribute, JS string): translations are text.
- `i18n.transliterate(text)` before a file name drops letters; `i18n.tag`/`i18n.name` read and name a language.
