## Voiceover mode

A narration will be laid over this animation. Here is its script, timed word by word (SRT):

```
{{SRT}}
```

- The animation is exactly as long as the voiceover: `duration` is the end time of the last cue.
- Each beat starts on the word that names it: take the start time of that word's cue from the SRT, and use it in
  `beats` and in `draw`. Things that are said should appear as they are said, not before.
- Never draw the narration or captions of it. The edit adds them. Short labels, numbers and titles are fine.
- In voiceover mode the player plays every effect about 8 dB quieter and leaves the beds out, so the voice sits on
  top; the edit mixes the render's sound under the voice. Keep effects sparse while someone is speaking; land the
  bigger ones in pauses.
