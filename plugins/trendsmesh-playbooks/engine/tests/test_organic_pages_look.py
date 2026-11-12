"""Issue #60: Organic AI video's own pages (the proposals, the week, the script, the intake, the models and the
week's delivery) in the TrendsMesh look of the shared run page: its colours and font (assets/page/theme.css), and its
top bar, the mark and name with an "Organic AI video" pill (`organic_pages.look`). No private data."""

import re

import pytest

from tm import i18n, organic_pages
from tm.run_page import template

FONT_LINK = ('<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700'
             '&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">')
OLD = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title>'
       '<link rel="preconnect" href="https://fonts.googleapis.com">' + FONT_LINK +
       '<style>:root{--accent:#B7791F}</style></head><body><div class="wrap"><header><h1>T</h1></header>'
       '<div class="wrap">inner</div></div></body></html>')


def _bar(page: str) -> str:
    return re.search(r'<header class="top">.*?</header>', page, re.S).group(0)


def test_a_page_gets_the_top_bar_with_the_playbooks_name_first_in_its_wrap():
    page = organic_pages.look(OLD, "en")
    bar = _bar(page)
    assert page.index('<div class="wrap">' + bar) == page.index('<div class="wrap">')   # the first thing on the page
    assert page.count('<header class="top">') == 1                                  # one bar, not one per wrap
    assert template.mark_svg() in bar and "<span>TrendsMesh</span>" in bar
    assert '<span class="pill dark">Organic AI video</span>' in bar
    assert bar == template.top_bar("Organic AI video", "TrendsMesh")                         # the run page's own bar


def test_a_page_takes_the_theme_and_the_run_pages_font():
    page = organic_pages.look(OLD, "en")
    assert "Source+Sans" not in page and "Source Sans" not in page
    assert page.count("fonts.googleapis.com/css2") == 1 and template.E(template.FONTS) in page
    style = re.search(r'<style id="tm-look">(.*?)</style></head>', page, re.S).group(1)
    assert page.index('<style id="tm-look">') > page.index("--accent:#B7791F")      # after the page's own colours
    for token in ("--cream: #fff4e6", "--pink-text: #d6246e", "--font: \"Bricolage Grotesque\""):
        assert token in style                                                       # read from assets/page/theme.css
    for old in ("--bg:var(--cream)", "--surface:var(--paper)", "--accent:var(--pink-text)", "--body:var(--font)",
                "--muted:var(--ink-soft)"):
        assert old in style                                                         # the page's names, in the theme
    # one light look, as the run page: the dark scheme's colours are the light ones too
    assert ':root:not([data-theme="light"])' in style and ':root[data-theme="dark"]' in style
    assert "color-scheme: light" in style and ".top {" in style and ".pill.dark {" in style


def test_the_look_is_made_once():
    once = organic_pages.look(OLD, "en")
    assert organic_pages.look(once, "en") == once


def test_a_polish_page_names_the_playbook_in_polish():
    bar = _bar(organic_pages.look(OLD.replace('lang="en"', 'lang="pl"'), "pl"))
    assert '<span class="pill dark">Organiczne wideo AI</span>' in bar and "<span>TrendsMesh</span>" in bar


def test_a_language_without_the_run_pages_words_has_the_brand_in_english(monkeypatch):
    """A language translated for the organic pages only (`tm i18n`) names the playbook in its own words."""
    real = i18n.translator

    def organic_only(lang):
        tr = real(lang)
        if i18n.is_english(tr.lang):
            return tr

        def words(key, **values):
            if key.startswith("run_page."):
                raise i18n.Missing(key)
            return "XX·" + tr(key, **values)
        return words

    monkeypatch.setattr(i18n, "translator", organic_only)
    bar = _bar(organic_pages.look(OLD, "pl"))
    assert '<span class="pill dark">XX·Organiczne wideo AI</span>' in bar and "<span>TrendsMesh</span>" in bar


def test_the_pill_names_the_playbook_as_the_run_page_does():
    for lang in ("en", "pl"):
        tr = i18n.translator(lang)
        assert tr(organic_pages.PLAYBOOK_KEY) == tr("run_page.playbook.organic_video")


@pytest.mark.parametrize("text", ["<script>window.x = 1;</script>", '{"a": "<div class=\\"wrap\\">"}', ""])
def test_a_part_of_a_page_is_left_as_it_is(text):
    assert organic_pages.look(text, "en") == text                                   # no <head>: not a page


def test_a_reference_page_is_worded_in_the_look():
    """The goldens of the reference tool (proposals, week, the edit check-in) are compared as the plugin builds
    them (`worded`): in the look, so they need no new golden."""
    assert organic_pages.worded(OLD, "en") == organic_pages.look(OLD, "en")
    assert _bar(organic_pages.worded(OLD.replace('lang="en"', 'lang="pl"'), "pl")) == _bar(
        organic_pages.look(OLD, "pl"))
