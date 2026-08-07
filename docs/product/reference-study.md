# Étude des références visuelles

## User-provided reference set

The nine screenshots establish two complementary interface modes:

1. **Monochrome operational dashboards**
   - Dense but calm information hierarchy.
   - Thin rules and flat surfaces replace decorative shadows.
   - Metrics appear in ledgers, tables, and aligned modules rather than repeated floating cards.
   - Black, white, and neutral gray dominate; state colors are sparse.

2. **Spatial industrial control views**
   - A plant map or isometric scene carries the primary task.
   - Navigation and filters stay peripheral.
   - Selection opens a contextual inspector without losing spatial context.
   - Status is encoded directly on equipment and reinforced with text.

## Live references studied

### Carbon Design System
Desktop and mobile screenshots: `/tmp/reference-carbon-desktop.png`, `/tmp/reference-carbon-mobile.png`.

Learnings:
- A strict grid can carry complex technical content without card decoration.
- Navigation labels remain direct and task-oriented.
- Dense controls use square geometry and visible separators.
- Mobile prioritizes one dominant surface and collapses secondary navigation.

### IBM Design Language
Desktop and mobile screenshots: `/tmp/reference-ibm-desktop.png`, `/tmp/reference-ibm-mobile.png`.

Learnings:
- Large spatial media can coexist with a precise utility shell.
- Grid lines are structural, not decorative.
- Typography has generous leading even when the interface is dense.
- A dark visual field is strongest when isolated from a light application shell.

### Grafana
Desktop and mobile screenshots: `/tmp/reference-grafana-desktop.png`, `/tmp/reference-grafana-mobile.png`.

Learnings:
- Operational products need strong contrast and explicit action hierarchy.
- Mobile copy must reflow without compressed headings.
- Marketing patterns and operations patterns should remain separate.
- Large promotional gradients and social-proof conventions do not fit IDDRV’s authenticated operations product.

## Principles adopted
- Treat the workshop as a spatial instrument, not a decorative card.
- Use flat ledgers and rules for analytical pages.
- Keep one green signal color for selection and confirmed state.
- Use amber and red only for watch and incident states.
- Let typography breathe; avoid condensed fallback fonts.
- Recompose mobile views rather than shrinking desktop tables.

## Principles rejected
- Generic hero sections inside operational routes.
- Glass, glow, gradient headlines, and floating rounded cards.
- Fake live-state indicators.
- Marketing social proof, unsupported savings, or inactive controls.
- Dark mode across every route; darkness is reserved for spatial fields when useful.
