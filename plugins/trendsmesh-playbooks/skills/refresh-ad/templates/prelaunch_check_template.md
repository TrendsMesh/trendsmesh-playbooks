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
| 1 | AI content labelling, where Meta requires it (AI video, AI-generated people or scenes) | | |
| 2 | Claims: health, financial, "before and after", references to institutions | | |
| 3 | Music licence for advertising (trending organic sounds are not licensed) | | |
| 4 | Voice licence (the intake confirmation; a cloned or new voice's rights) | | |
| 5 | Text on the image: legible in the feed preview, inside the safe zones, no spelling errors | | |
| 6 | Known visual defects, with their time (none left that the user did not accept) | | |
| 7 | Quality against the original (the before and after pair on the review page) | | |

**Result:** green (every item green) or red (the red items, and what fixes each).

Record it with `tm decide E2b green|red --by rule --note "<this file>: <summary>"`. After a fix,
check again in a new version and record it with `--change`.
