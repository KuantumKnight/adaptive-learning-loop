# Accessibility verification

## Verified in the live localhost browser

- Question controls expose semantic button names and selected state through the
  accessibility tree.
- Form controls expose labels for participant code, lesson, purpose, camera
  consent, and researcher credential.
- The support surface uses `role="dialog"`, `aria-modal`, and a labelled
  heading. Opening it moves focus to the dialog; Escape dismisses it.
- Keyboard focus is visibly outlined on the header control and all interactive
  controls use `:focus-visible` styling. A live Tab traversal reached the
  participant input, lesson selector, rule-based mode button, personalized mode
  button, and camera consent input in document order.
- Answer choices use dark readable text on the light panel palette after visual
  inspection.
- The visualizer communicates its trace in a live text message and does not
  depend on animation.
- An axe 4.12.1 audit of the live start page reports zero WCAG violations
  after darkening muted text and changing primary actions to white-on-mint. The
  live lesson page has also passed the same audit. The remaining incomplete
  heuristic is gradient-based contrast detection plus the visual-only local
  webcam preview; both require manual review rather than indicating a failing
  text control.
- A live 320×844 reduced-motion pass showed the start form scrolling vertically
  without horizontal clipping; all mode controls, camera consent, and primary
  actions remained readable and reachable. The viewport was restored to
  1280×900 afterward.
- A 640px-wide viewport proxy for 200% browser zoom showed the responsive
  single-column layout with `scrollWidth == innerWidth` and no horizontal
  overflow. The viewport was restored to 1280×900.

## Remaining manual checks

- Run a screen reader on Windows and confirm the complete lesson order.
- Inspect 320px, tablet, and desktop layouts with real content and the modal
  open.
- Check contrast with an automated tool after the final visual theme is frozen.
- Test browser zoom at 200% and reduced-motion settings on the target browser.
