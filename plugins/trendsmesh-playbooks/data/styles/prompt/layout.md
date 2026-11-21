## A stills video: the layout of the trend's format

This video is made of stills: the run's picked pictures, laid out and animated in the format the trend's own videos
use (a tips list, a before and after, a ranking, a quiz, a step by step ...). You build that layout as your style
module, the same way an animation is built, and it is rendered the same way.

- **The format** comes from the trend's videos, described here (the pack's style spec: the layout, the font class,
  the colours, the number style, the extras, and the videos it was read from):

```json
{{STYLE_SPEC}}
```

  Copy the format: where each picture, the title, the numbers and the labels sit, how long each item stays, how one
  item gives way to the next, the number style and the extras. The rendering (lettering, finishing, motion,
  transitions, sound) is the style's, below; where the style spec names colours or a font class, use them for the
  format's own parts (title bars, number badges, labels).
- **The pictures** are already in the page: draw each with `Player.picture(ctx, name, x, y, w, h, { fit: "cover" |
  "contain", radius, focus: [fx, fy] })` (cover by default: the box filled and cropped around `focus`; it returns
  false when the page has no such picture). `Player.pictures()` lists them with their sizes. Never draw a picture of
  your own in their place, and never leave one out. The page has these pictures:

{{PICTURES}}

- **One beat per scene**: a beat per item of the format (usually one per picture, plus a title and a close when the
  format has them), each starting on its line of the voiceover. These beats replace the reference's kinds of beats.
- Keep the pictures the hero: they fill most of the frame, inside the safe area; text sits on bars or panels over
  them, never over a face.
- Then build its page with `tm organic atlas-page` (it inlines the pictures and runs the layout check; fix every
  finding in a new version) and draw it with `tm organic animate`. It is not a storyboard: build it in play mode.
