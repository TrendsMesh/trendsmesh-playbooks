# Script to film: “<title>” (<id>, vNN)

The Script output. The agent writes `03_wip/script_<id>_<lang>_vNN.json` (`engine/src/tm/schemas/pb3_script.schema.json` in the plugin), `tm organic script check` checks it, and `tm organic page script` renders it as a page plus this Markdown. Example, in the repository: `handoff/organic-video_v02/examples/<walkthrough run>/04_final/M5_script_en_v01/`.

<channel> · Format: <format> · Length: <15–17 s> · <n> words

**Goal:** what the viewer learns or feels.

Built on: <trends with numbers>.

## Hook (first 2 seconds)
> <line>

On screen: <text>. Why it works: <reason>.

## Shot list
| # | Time | Framing | Action | Line | On screen |
|---|---|---|---|---|---|
| 1 | 0–3 s | … | … | … | … |

## All lines (teleprompter)
<all lines in order>

## Filming
- Vertical 9:16, 1080p or 4K, 30 fps.
- Phone at eye level.
- Soft side light.
- A close mic.
- 2–3 takes.
- Keep half a second of silence before and after each line.
- Keep the face and gestures in the middle of the frame (safe zone).

## Edit
- Cut on the pauses.
- Punch in where the shot list says.
- Captions in short groups at the bottom of the safe zone; top texts above.
- Voice at about −14 LUFS.

## Posting kit
Per platform, as in `posting_kit_template.md`. When the creator films it, the AI label is not needed.

## Fact check (for you, not for the caption)
- <claim>: <source>.

## Generate instead of filming (optional)
A note with the model and its cost, a host image prompt (GPT Image 2) and a video prompt (MiniMax H3, dialogue in the prompt).
