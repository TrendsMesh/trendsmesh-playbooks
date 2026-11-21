## An animatic of a brief

This animation is an **animatic**: a short animated storyboard of one concept of a creative brief, shown to the team or a
creator before anyone films. It is not an explainer, and it is not the finished video: it shows the structure, the
timing, the on-screen text, the hook and the call to action, drawn in the {{STYLE_NAME}} style. The topic above is
the concept, beat by beat.

- **The beats are the brief's.** One beat of your module per beat of the concept, in its order: `beats` holds each
  beat's start time exactly as the topic gives it, written out as a list in `Player.register` (`beats: [0, 3, 9]`,
  so the command that draws it can count them), and `duration` is the concept's length ({{DURATION}}). These beats
  replace the reference's kinds of beats (a title, a diagram, a key number): draw a diagram or a number only where a
  beat shows one.
- **What each beat shows** is its "Seen" line: the person, the place, the product and the action, drawn in the
  style's medium. Draw people as the style draws figures, never a real person or a real brand other than the
  product, and keep the product's name as the brief writes it.
- **The on-screen texts** are the beat's own, word for word, where the brief puts them (top, center or bottom of
  the frame, a box, a label, the closing call to action), from the time it gives. Keep the hook readable at a glance
  in the first beat and clear of faces and of the product.
- **The "Heard" line** is the voiceover or the dialogue: show it as a small caption low in the safe area, never as a
  second headline. There is no recorded voice: the sound is the style's sound kit only, sparse.
- **Pictures of the product** the page holds, from the brief: draw each with
  `Player.picture(ctx, name, x, y, w, h, { fit: "contain" })` in the beat it is named after, and leave none out.
  With none, draw the product (its screen, its pack) in the style's medium, with its name as the brief writes it.

{{PICTURES}}

- You write only the module. `tm brief animatic --render` builds its page for each format, runs the layout check
  and draws it; a finding comes back to be fixed in a new version of the module.
