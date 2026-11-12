# Template: quality and policy check (`04_final/prelaunch_check_vNN.md`, R8)

Every variant passes this check before activation, at every level of involvement. **A red item
blocks the launch, also in Hands-off.** Each item is green or red, with its evidence (a file, a
frame, a preview, the user's confirmation). Written in the run's language.

---

| Variant | File | Preview checked |
|---|---|---|

For each variant:

| # | Item | Green / red | Evidence |
|---|---|---|---|
| 1 | AI disclosure: any media created or edited with a generative AI tool (a cloned or synthetic voice, generated music, frames inpainted by a model such as ProPainter (not the free OpenCV plate), an AI shot or video, generated people or scenes). Check, never ask: the `self_ai_disclosure` on the creative matches the plan's decision (asked before the upload) and what the run made with AI (`tm ai-media` on the final files). Red if it differs, or the creative has none while the run used generative AI | | |
| 2 | Claims: health, financial, "before and after", references to institutions | | |
| 3 | Music licence for advertising (trending organic sounds are not licensed) | | |
| 4 | Voice licence (the intake confirmation; a cloned or new voice's rights) | | |
| 5 | Text on the image: legible in the feed preview, inside the safe zones, no spelling errors | | |
| 6 | Known visual defects, with their time (none left that the user did not accept) | | |
| 7 | Quality against the original (the before and after pair on the run page) | | |
| 8 | Formats and placements: each ad built (control and variants) has the files the plan names per placement (9:16 in Reels and Stories, 4:5 in feed, through placement asset customization), the same for the control and the variants, and the control is a new creative of the original's files, not the original's creative id (unless the plan names the exception: a new creative can't match the original, for example a partnership ad run from a creator's account); red on any difference from the approved plan | | |

**Result:** green (every item green) or red (the red items, and what fixes each).

Record it with `tm decide E2b green|red --by rule --note "<this file>: <summary>"`. After a fix,
check again in a new version and record it with `--change`.
