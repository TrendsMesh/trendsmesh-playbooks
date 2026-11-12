"""What an open stage lets the user save beside the choice (its **detail**), and the check of what the page saved.

Some stages ask for more than one choice and a note: a pick among concepts, accept / redo / drop for each item of a
gate, a note per scene, notes pinned at a version's time, the copy's texts edited and ticked. Their blocks offer
these as inputs (`template` renders them only in an open stage of a page that can save), and each block says what
it offers in its `offer`: `{field: spec}`. The build keeps the offer of every open check-in (`.build.json`
`offer`), and the page saves the inputs as `detail` in the same document as the choice (`decisions/<checkin>`).

`check(offer, detail)` takes back only what was offered, in the offered shape; anything else is a problem, so a
saved value is never acted on unless the page offered it. The specs:

    {"type": "pick", "values": [...]}                 one of the values (a concept, a version)
    {"type": "each", "keys": [...], "values": [...]}  per key one of the values (a gate's items)
    {"type": "notes", "keys": [...]}                  per key a text (a scene's note); empty ones are dropped
    {"type": "pins", "versions": [...]}               a list of {version, t (seconds), text} (review notes)
    {"type": "copy", "ads": {ad: {list: count}}}      per ad, per list, per text number {text, keep}
"""

from __future__ import annotations

MAX_TEXT = 4000
MAX_PINS = 200


def merge(offers: list[dict]) -> dict:
    """One offer from the blocks' offers (a later block's field never replaces an earlier one's)."""
    out: dict = {}
    for offer in offers:
        for field, spec in (offer or {}).items():
            out.setdefault(field, spec)
    return out


def _text(value: object) -> bool:
    return isinstance(value, str) and len(value) <= MAX_TEXT


def _num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def check(offer: dict, detail: object) -> tuple[dict, list[str]]:
    """The saved `detail` as far as `offer` offered it, and what was not offered (in words)."""
    if detail in (None, {}):
        return {}, []
    if not isinstance(detail, dict):
        return {}, ["the page's detail is not an object"]
    out: dict = {}
    problems: list[str] = []
    for field, value in detail.items():
        spec = (offer or {}).get(field)
        if spec is None:
            problems.append(f"{field!r} is not something this question offered")
            continue
        kind = spec.get("type")
        if kind == "pick":
            if value in (None, ""):
                continue
            if value not in spec.get("values", []):
                problems.append(f"{field}: {value!r} is not one of {', '.join(map(str, spec.get('values', [])))}")
            else:
                out[field] = value
        elif kind == "each":
            if not isinstance(value, dict):
                problems.append(f"{field} is not a set of choices")
                continue
            got = {}
            for key, v in value.items():
                if v in (None, ""):
                    continue
                if key not in spec.get("keys", []) or v not in spec.get("values", []):
                    problems.append(f"{field}: {key!r} = {v!r} was not offered")
                else:
                    got[key] = v
            if got:
                out[field] = got
        elif kind == "notes":
            if not isinstance(value, dict):
                problems.append(f"{field} is not a set of notes")
                continue
            got = {}
            for key, v in value.items():
                if key not in spec.get("keys", []) or not _text(v):
                    problems.append(f"{field}: the note for {key!r} was not offered or is not text")
                elif v.strip():
                    got[key] = v.strip()
            if got:
                out[field] = got
        elif kind == "pins":
            if not isinstance(value, list) or len(value) > MAX_PINS:
                problems.append(f"{field} is not a list of notes (at most {MAX_PINS})")
                continue
            got = []
            for pin in value:
                if not (isinstance(pin, dict) and pin.get("version") in spec.get("versions", [])
                        and _num(pin.get("t")) and pin["t"] >= 0 and _text(pin.get("text"))):
                    problems.append(f"{field}: a note does not name an offered version, a time and its text")
                elif pin["text"].strip():
                    got.append({"version": pin["version"], "t": round(float(pin["t"]), 2), "text": pin["text"].strip()})
            if got:
                out[field] = sorted(got, key=lambda p: (spec["versions"].index(p["version"]), p["t"]))
        elif kind == "copy":
            ads = spec.get("ads") or {}
            if not isinstance(value, dict):
                problems.append(f"{field} is not the copy's texts")
                continue
            got = {}
            for ad, lists in value.items():
                if ad not in ads or not isinstance(lists, dict):
                    problems.append(f"{field}: the ad {ad!r} was not offered")
                    continue
                for name, items in lists.items():
                    count = ads[ad].get(name)
                    if count is None or not isinstance(items, dict):
                        problems.append(f"{field}: {ad} {name!r} was not offered")
                        continue
                    for n, item in items.items():
                        if not (str(n).isdigit() and 1 <= int(n) <= count and isinstance(item, dict)
                                and _text(item.get("text", "")) and isinstance(item.get("keep", True), bool)):
                            problems.append(f"{field}: {ad} {name} text {n!r} was not offered")
                            continue
                        got.setdefault(ad, {}).setdefault(name, {})[str(int(n))] = {
                            "text": str(item.get("text", "")), "keep": item.get("keep", True)}
            if got:
                out[field] = got
        else:
            problems.append(f"{field}: the offer has no type the page knows")
    return out, problems
