## Storyboard first

Do not build the animation yet. First build only the storyboard page, then stop.

- It is the same style module, built into a page in storyboard mode. The runtime then draws one {{WIDTH}}x{{HEIGHT}}
  panel per beat (canvases `p1` ... `pN`), sets `window.STORYBOARD_READY = true` and offers `window.makeSheet()`
  for a contact sheet.
- Plan 5 or 6 beats. Give each a clear name in `beatNames`. By default each panel shows the frame 60 % of the way
  into its beat; set `stills` (one time per panel) when another moment tells the beat better.
- Draw the panels for real, in the full style: the same subjects, colours, lettering and finishing in every panel,
  so the storyboard shows exactly what the animation will look like.
- `draw` and `score` should already be the real ones, so the approved storyboard's module becomes the animation
  (built again in play mode, with the notes on the storyboard applied).
- Then stop. Show the storyboard, list the beats with their times in one line each, and wait for approval or changes
  before you build the animation.
