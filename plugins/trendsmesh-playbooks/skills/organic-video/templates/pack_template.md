# <id>, pack vNN: “<title>”

Written in the chat language. The AI video's pack: the plugin writes it as JSON (`tm organic pack check`) and the engine renders this Markdown from it. Examples, in the repository:
- `handoff/organic-video_v02/examples/<walkthrough run>/03_wip/M1/pack_v01.md` (animation);
- `handoff/organic-video_v02/examples/pet-store-proposals/03_wip/packs/packs_v03.md` (footage, talking dog, sections).

Channel: <name> (<platforms>). Level: <Check every step / Just the big calls / Hands-off>. Product: <level + how>. User's taste picks: <style, voice, music>.

## Script (<n> words, ~<s> s at ~2.8–3 words/s)
1. “<line 1>” (hook)
2. …

## Picture
| Line / time | What we see |
|---|---|
| 1 | … |

On-screen text: what appears and when. Everything important stays inside the safe zone. Animations keep it above y 1260.

## Sound
- Voice: native H3 dialogue in the prompt, or an ElevenLabs narrator <voice>.
- Music: <folder track / Mixkit / trending sound added in the app / none>.
- Target loudness: −14 LUFS.

## Model and production
- Model per component, with the reason, ranking and live price (date checked).
- Recipe read: `references/model-prompting/<model>.md` at the plugin root.
- Stages: <images → takes / storyboard → animation> → edit.
- Resolution: 768P $<x> / 1080p $<y> / 768P + Pruna $<z>.

## Facts and sources (for the pack only, never in the post text)
- <claim>: <source link>.

## Check-ins
1. Pack + cost (at every level).
2. Images (or storyboard + VO).
3. Video.
4. Final edit + posting kit.

## Cost
| Step | Model / tool | Cost |
|---|---|---|
| … | … | $… |
| **Total** | | **$…** of the $<budget> budget |

**Risk:** low / medium / high. List each risk hit and its mitigation.
