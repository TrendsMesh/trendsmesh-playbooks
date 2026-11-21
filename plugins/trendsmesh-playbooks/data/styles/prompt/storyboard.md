## Storyboard first

Do not build the animation yet. First build only the storyboard page, then stop.

- It is the same style module, built into a page in storyboard mode. The runtime then draws one {{WIDTH}}x{{HEIGHT}}
  panel per beat (canvases `p1` ... `pN`), sets `window.STORYBOARD_READY = true` and offers `window.makeSheet()`
  for a contact sheet.
- One beat per scene of the content: as many beats as the content's scenes (the frames list's panels), in their
  order, each starting on its scene's time. Give each a clear name in `beatNames`. The page is refused when the count
  differs from the frames list's. Each panel shows the end of its beat, 0.2 s before the next beat starts (the length
  minus 0.2 s for the last), where the scene is complete: have each scene finished by then. Set `stills` (one time per
  beat) only when another moment tells a beat better.
- Draw the panels for real, in the full style: the same subjects, colours, lettering and finishing in every panel,
  so the storyboard shows exactly what the animation will look like.
- `draw` and `score` should already be the real ones, so the approved storyboard's module becomes the animation
  (built again in play mode, with the notes on the storyboard applied).
- Then stop. Show the storyboard, list the beats with their times in one line each, and wait for approval or changes
  before you build the animation.
