"""A refused reference image (issue #137 item 6; the owner's decision #148 line 19): one free retry, then the user picks.

A paid video call that sends the approved casting or host still as a reference (`reference_images`,
`reference_image_urls`, any `reference_*` image input) may end `failed` with a content refusal (Replicate's E006,
"prohibited content"): nothing is spent, and `tools/replicate_run.py` records `"refused_reference": "<file>"` in the
run record (`refused`). The paid-call guards (`tm.create_plan:guard` for Create an ad, `tm.organic_specs:guard` for
Organic AI video) hold the item to `gap`:

- after one refusal, exactly one more call of the item runs, with the same reference image and the same prompt (the
  refused prediction cost $0, so it is the item's own approved line, no new approval);
- after a second refusal of the same reference, no call of the item runs until the user picks, at every level, the
  on-demand check-in `refused_reference` (`tm decide refused_reference <choice> --said "<their words>" --note
  "<the refused record>"`, the note naming which refusal it answers): `retry` (one more call, the same reference),
  `other_model` (another model that takes a reference image, priced first: a call with another model, the reference
  still sent) or `no_reference` (a call without the reference image). The question says `WARNING`;
- a call of a refused item that leaves the reference out is refused unless the user picked `no_reference`: the
  approved casting is never dropped without asking.

Reads only.
"""

from __future__ import annotations

import re
from pathlib import Path

CHECKIN = "refused_reference"
CHOICES = ("retry", "other_model", "no_reference")
FAILED = ("failed", "canceled")
REFUSAL = re.compile(r"\bE006\b|prohibited content|content (?:guidelines|policy|policies)|safety (?:filter|system)",
                     re.IGNORECASE)
WARNING = ("Without the reference image, the face in the ad will not be the one you approved in casting.")
_NOT_IMAGES = ("audio", "video")


def reference_keys(inputs: dict) -> list[str]:
    """The inputs that send a reference image: `reference_*` keys that are not audio or video, with a value."""
    return [k for k, v in (inputs or {}).items() if k.startswith("reference_") and not any(w in k for w in _NOT_IMAGES)
            and v not in (None, "", [])]


def _name(value: object) -> object:
    """A file input as its name: a recorded `file:<name>` or a path, both to `<name>`; a list item by item."""
    if isinstance(value, list):
        return tuple(_name(v) for v in value)
    text = str(value)
    if text.startswith("file:"):
        text = text[len("file:"):]
    return Path(text.replace("\\", "/")).name if not text.startswith(("http://", "https://")) else text


def reference_of(inputs: dict) -> str | None:
    """The reference image a call sends (the first of the first reference input), as recorded, or None."""
    keys = reference_keys(inputs)
    if not keys:
        return None
    value = inputs[keys[0]]
    first = value[0] if isinstance(value, list) and value else value
    return str(first)


def refused(record: dict) -> str | None:
    """The reference file a failed prediction was refused with (a content refusal of a call with a reference), or
    None. What `replicate_run` writes as the record's `refused_reference`."""
    error = str(record.get("error") or "")
    if record.get("status") not in FAILED or not REFUSAL.search(error) or "first frame" in error.lower():
        return None                                     # H3's own E006 (a first frame with references) is no refusal
    return reference_of(record.get("input") or {})


def _sends(inputs: dict, reference: str) -> bool:
    want = _name(reference)
    return any(want == _name(v) or (isinstance(v, list) and want in _name(v)) for k, v in (inputs or {}).items()
               if k in reference_keys(inputs))


def _same(spec_input: dict, record_input: dict) -> bool:
    """The call is the refused one again: the same prompt and the same reference inputs."""
    if (spec_input or {}).get("prompt") != (record_input or {}).get("prompt"):
        return False
    keys = set(reference_keys(spec_input)) | set(reference_keys(record_input))
    return all(_name((spec_input or {}).get(k)) == _name((record_input or {}).get(k)) for k in keys)


def _pick(decisions: list[dict], names: list[str]) -> tuple[int, dict] | None:
    """The latest `refused_reference` decision whose note names one of the item's records: (that record's index,
    the decision), or None."""
    for d in reversed(decisions or []):
        if d.get("checkin") != CHECKIN:
            continue
        said = f"{d.get('note') or ''} {d.get('said') or ''}"
        hits = [i for i, n in enumerate(names) if n and n in said]
        if hits:
            return max(hits), d
    return None


def command(record: str) -> str:
    return (f"tm decide {CHECKIN} <retry|other_model|no_reference> --run R --said \"<their words>\" --note "
            f"\"{record}\"")


def gap(records: list[tuple[Path, dict]], spec: dict, decisions: list[dict], item: str,
        warning: str = WARNING) -> str | None:
    """Why this call of `item` may not run yet (the module docstring), or None. `records` are the item's run records,
    oldest first (`organic_specs.records`); `spec` the call's (`model`, `input`)."""
    names = [p.name for p, _ in records]
    refusals = [(i, r) for i, (_, r) in enumerate(records) if r.get("refused_reference") or refused(r)]
    if not refusals or any(r.get("status") in ("done", "succeeded") for _, r in records[refusals[-1][0] + 1:]):
        return None                                     # never refused, or a later call made it
    picked = _pick(decisions, names)
    since = [(i, r) for i, r in refusals if picked is None or i > picked[0]]
    i_last, last = refusals[-1]
    reference = str(last.get("refused_reference") or refused(last))
    inputs = spec.get("input") or {}
    model = str(spec.get("model") or "").split(":", 1)[0]
    choice = picked[1].get("choice") if picked else None
    ask = (f"Ask the user, at every level: \"{warning}\" Their choices: try once more with the same reference image; "
           "another model that takes a reference image (price it first, a new plan or pack version, and show the "
           "cost); or go without the reference image. Record their pick: " + command(names[i_last]) + ".")
    if choice == "no_reference" and not since:
        return None                                     # the user chose to go on without it
    if not _sends(inputs, reference):
        return (f"{item}'s call leaves out the reference image {_name(reference)}, which was refused "
                f"({names[i_last]}), and the user has not chosen to go without it. {ask}")
    if choice == "other_model" and not since:
        refused_model = str(last.get("model") or "").split(":", 1)[0]
        if model == refused_model:
            return (f"The user chose another model for {item}, and this call runs {model} again, the model that "
                    f"refused {_name(reference)}. Run the model they chose, priced first. {ask}")
        return None
    if choice == "retry" and not since:
        if not _same(inputs, last.get("input") or {}):
            return (f"The user chose to try {item} once more as it was: send the same prompt and the same reference "
                    f"image as {names[i_last]}.")
        return None
    if picked is None and len(since) == 1:
        if not _same(inputs, last.get("input") or {}):
            return (f"{names[i_last]} was refused with the reference image {_name(reference)} (a content refusal, "
                    f"nothing spent). The one free retry sends the same prompt and the same reference image; a "
                    f"changed call is asked first. {ask}")
        return None
    return (f"{item} was refused {len(refusals)} times with the reference image {_name(reference)} (nothing spent), "
            f"so nothing more of it runs until the user picks. {ask}")
