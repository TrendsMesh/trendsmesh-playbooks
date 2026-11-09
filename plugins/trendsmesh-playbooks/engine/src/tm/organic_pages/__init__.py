"""Organic video's pages (playbook 03): ports of the handoff's page builders (`tools/pb3/`), one module each.

    proposals   the proposals page (C2), `tm organic page proposals`
    script      the script to film (E3), `tm organic page script`
    gate        the check-in pages (F1 images, F2 takes) and the delivery page (G4), `tm organic page gate|delivery`;
                the week's delivery page (I4, `tm organic deliver-week`)
    week        the week plan (I2), `tm organic page week`

Shared here:
- `CAPABILITIES[page]`: what each page declares with `declare_capabilities` after its first publish
  (HANDOFF "publish first, then declare capabilities"). A page's db holds one collection; its rules
  let the owner read and write that collection and every document in it (PB02's rule shape,
  `brief_page.CAPABILITIES`). `downloads` is the original's own (`window.claude.use('downloads')` in
  gate_page.py and script_page.py). The live check against `describe_capabilities` is acceptance's
  (fixtures/organic/README.md).
- `UI[lang]`: the plugin's own words on a page, per page language (en, pl): `levels`, named exactly
  as the plugin names them (plan Global Constraints; the Polish names wait on the playbook owner), `wording`,
  the original's strings that its Polish table leaves in English -> Polish, and `gate`, the titles, ledes,
  questions, labels and captions `tm.organic_gates` writes into the check-in and delivery pages.
- `WORDING`: the original's visible strings -> the plugin's (plan Decision 10: "check-in", never "gate";
  the levels in place of its "A–Z"). `worded` applies it, then `UI[lang]["wording"]`: the one
  wording table. Each builder applies it to the page after the original's `localize`; the equality tests
  apply it to the golden made by the reference tool.
- `CSS` (pages.css): the reference pages' stylesheet, verbatim.
"""

from __future__ import annotations

from pathlib import Path

CSS = (Path(__file__).parent / "pages.css").read_text(encoding="utf-8")
LANGS = ("en", "pl")


def _db(*collections: str) -> dict:
    return {"rules": [{"path": c, "read": "owner", "write": "owner"} for c in collections]}


CAPABILITIES: dict[str, dict] = {
    "proposals": {"db": _db("decisions"), "user": {"scopes": ["profile"]}},
    "gate": {"db": _db("gate_images", "gate_video", "gate_edit"), "user": {"scopes": ["profile"]}, "downloads": {}},
    "script": {"downloads": {}},
    "week": {"db": _db("week"), "user": {"scopes": ["profile"]}},
}

def _ideas(n: int) -> str:
    """"pomysł", "pomysły" or "pomysłów" after the number n (1–9)."""
    return "pomysł" if n == 1 else "pomysły" if 2 <= n <= 4 else "pomysłów"


UI: dict[str, dict] = {
    "en": {"levels": {"every_step": "Check every step", "big_calls": "Just the big calls", "hands_off": "Hands-off"},
           "wording": [], "gate": {}},
    "pl": {"levels": {"every_step": "Sprawdzaj każdy krok", "big_calls": "Tylko najważniejsze decyzje",
                      "hands_off": "Bez zatrzymywania"},
           # what the original's Polish table leaves in English: the proposals page's lede
           "wording": [*((f'<p class="lede">{n} video ideas for ', f'<p class="lede">{n} {_ideas(n)} na filmy dla ')
                         for n in range(1, 10)),
                       ("), each built on trends rising now, with the evidence videos behind it. Pick the ones to "
                        "produce; nothing is generated or paid until you approve a pack and its cost.",
                        "), każdy oparty na trendach, które rosną teraz, z filmami-dowodami. Wybierz te do produkcji; "
                        "nic nie jest generowane ani opłacane, dopóki nie zatwierdzisz paczki i jej kosztu.")],
           "gate": {}},
}

WORDING: list[tuple[str, str]] = [
    # the check-in and delivery pages' eyebrow (the original's "gate: <gate>"; Polish "bramka: …")
    ("Organic AI video · gate: edit", "Organic AI video · check-in: final edit"),
    ("Organic AI video · gate: ", "Organic AI video · check-in: "),
    ("Organiczne wideo AI · bramka: ", "Organiczne wideo AI · punkt kontrolny: "),
    # the proposals page's hint under Hands-off (the original's "A–Z")
    ("A–Z: Claude produces the whole video without stopping.", "Hands-off: Claude produces the whole video without stopping."),
    ("A–Z: Claude robi cały film bez zatrzymywania się.", "Bez zatrzymywania: Claude robi cały film od początku do końca."),
]


def lang_of(data: dict) -> str:
    """The page language: the file's `lang` when it is en or pl, else en (plan Decision 10)."""
    lang = data.get("lang") if isinstance(data, dict) else None
    return lang if lang in LANGS else "en"


def worded(page: str, lang: str) -> str:
    """The page with `WORDING`, then its language's `UI[lang]["wording"]`, applied."""
    for old, new in [*WORDING, *UI[lang]["wording"]]:
        page = page.replace(old, new)
    return page


UI["en"]["gate"] = {
    "title_images": "{title}: the images",
    "title_video": "{title}: the takes",
    "title_edit": "{title}: the final video and its posting kit",
    "lede_images": ("The images made for this video, beside the product and the references. Pick one where there is "
                    "a choice, then Accept, Redo with a note, or Drop. Nothing is made again until you say so."),
    "lede_video": ("Each take with its QA findings (720p previews), beside the references. Pick one where there is a "
                   "choice, then Accept, Redo with a note, or Drop. A video is never made again unless you ask."),
    "lede_edit": ("The final video, its cover and the posting kit, then every step that made it: the images, the raw "
                  "takes, the motion graphics, the voiceover, the storyboard and the QA findings. Every platform is "
                  "ticked; untick the ones you do not want. The YouTube thumbnail is optional (it shows outside the "
                  "Shorts feed). Download the video (1080p) and the cover with the Download buttons."),
    "proposal": "{id} · {channel}",
    "label_final": "{id} · “{title}”",
    "q_final": "Watch the video, check the cover and the texts. Untick a platform you do not want to post on.",
    "label_images": "Images: {name}",
    "q_images": "Which image of {name}?",
    "label_takes": "Takes: {name}",
    "q_takes": "Which take of {name}? The QA findings are under each take.",
    "label_voiceover": "Voiceover",
    "q_voiceover": "Listen to the pace, the pronunciation and the tone.",
    "label_storyboard": "Storyboard: {name}",
    "q_storyboard": "Do the look and the order fit? On Redo, say which panel to change and how.",
    "label_animation": "Animation: {name}",
    "q_animation": "Watch the animation with the voiceover in mind. On Redo, say which moment to change and how.",
    "label_motion": "Motion graphics: {name}",
    "q_motion": ("Watch the render: the pictures, the text and the timing. Accept the one the video is made from; "
                 "on Redo, say what to change."),
    "cap_final": "Final video {version}",
    "cap_cover": "Cover",
    "cap_packshot": "Product packshot",
    "cap_host": "Host image",
    "cap_evidence": "Evidence video by @{creator}",
    "cap_still": "The copied look, rendered ({comp}, frame {frame})",
    "cap_contact": "QA contact sheet of {take}",
    "dl_video": "video (1080p)",
    "dl_cover": "cover",
    "cover_file": "cover",
    "qa_pass": "QA passes",
    "qa_fails": "QA fails: {fails}",
    "qa_findings": "findings: {findings}",
    "qa_none": "no QA yet",
}
UI["pl"]["gate"] = {
    "title_images": "{title}: obrazy",
    "title_video": "{title}: ujęcia",
    "title_edit": "{title}: gotowy film i zestaw do publikacji",
    "lede_images": ("Obrazy zrobione do tego filmu, obok produktu i odniesień. Wybierz jeden tam, gdzie jest wybór, "
                    "potem Akceptuj, Popraw z uwagą albo Odrzuć. Nic nie powstaje od nowa bez Twojej prośby."),
    "lede_video": ("Każde ujęcie z wynikami kontroli jakości (podglądy 720p), obok odniesień. Wybierz jedno tam, gdzie "
                   "jest wybór, potem Akceptuj, Popraw z uwagą albo Odrzuć. Wideo nigdy nie powstaje od nowa bez "
                   "Twojej prośby."),
    "lede_edit": ("Gotowy film, okładka i zestaw do publikacji, a potem każdy krok, który do nich doprowadził: obrazy, "
                  "surowe ujęcia, grafika w ruchu, lektor, storyboard i wyniki kontroli jakości. Wszystkie platformy "
                  "są zaznaczone; odznacz te, których nie chcesz. Miniatura YouTube jest opcjonalna (pokazuje się poza "
                  "feedem Shorts). Film (1080p) i okładkę pobierzesz przyciskami „Pobierz”."),
    "proposal": "{id} · {channel}",
    "label_final": "{id} · „{title}”",
    "q_final": "Obejrzyj film, sprawdź okładkę i opisy. Odznacz platformę, jeśli nie chcesz na niej publikować.",
    "label_images": "Obrazy: {name}",
    "q_images": "Który obraz {name}?",
    "label_takes": "Ujęcia: {name}",
    "q_takes": "Które ujęcie {name}? Wyniki kontroli jakości są pod każdym ujęciem.",
    "label_voiceover": "Lektor",
    "q_voiceover": "Odsłuchaj tempo, wymowę i ton.",
    "label_storyboard": "Storyboard: {name}",
    "q_storyboard": "Czy taki wygląd i przebieg pasuje? Przy „Popraw” napisz, który kadr zmienić i jak.",
    "label_animation": "Animacja: {name}",
    "q_animation": "Obejrzyj animację, myśląc o lektorze. Przy „Popraw” napisz, który moment zmienić i jak.",
    "label_motion": "Grafika w ruchu: {name}",
    "q_motion": ("Obejrzyj render: obrazy, tekst i tempo. Zaakceptuj ten, z którego powstanie wideo; przy „Popraw” "
                 "napisz, co zmienić."),
    "cap_final": "Gotowy film {version}",
    "cap_cover": "Okładka",
    "cap_packshot": "Zdjęcie produktu",
    "cap_host": "Obraz prowadzącej osoby",
    "cap_evidence": "Film-dowód od @{creator}",
    "cap_still": "Skopiowany wygląd, wyrenderowany ({comp}, klatka {frame})",
    "cap_contact": "Arkusz kontroli jakości {take}",
    "dl_video": "wideo (1080p)",
    "dl_cover": "okładkę",
    "cover_file": "okladka",
    "qa_pass": "kontrola jakości: bez zastrzeżeń",
    "qa_fails": "kontrola jakości nie przeszła: {fails}",
    "qa_findings": "uwagi: {findings}",
    "qa_none": "jeszcze bez kontroli jakości",
}
