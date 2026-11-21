## The full animation, from the accepted storyboard

The storyboard is accepted. Build the full animation now, in play mode: do not stop after a storyboard, and do not
ask for approval again.

- Start from the accepted storyboard's module, `{{FROM}}` (its code is at the end of this prompt). Keep its beats,
  their names and times, its subjects, its setting and its style exactly; the animation must look like the panels
  the user accepted.
- Apply the user's notes on the storyboard, and change nothing else:

{{NOTES}}

- Fill in the motion between the panels: entrances, transitions and the camera, as the reference module does, so
  each beat is complete at the moment its panel showed (0.2 s before the next beat starts).
- Write the animation as a new module in the same folder (`explainer_vNN.js`, the next version), never over the
  storyboard's. Then build its page with `tm organic atlas-page` (without `--storyboard`): it runs the layout check,
  and every finding is fixed in a new version before anything is drawn. Then draw it with `tm organic animate`
  (the brief names both commands with their options).
