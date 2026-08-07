# Plan de redesign frontend IDDRV

## Design read
Reading this as a full redesign of an authenticated industrial operations application for production, quality, methods, supervision, and administration roles, with a precise monochrome language and a spatial workshop as its signature instrument.

## Audit summary

### What works
- Real React routes and TanStack Query boundaries already exist.
- Loading, empty, error, and success primitives are present.
- The workshop supports 2D, optional Three.js, replay, and keyboard-accessible machine selection.
- Incident evidence, hypotheses, and human feedback form a credible product-specific workflow.
- The local/on-premise constraint is consistently represented.

### What needs correction
- Legacy cyber-dark CSS and newer editorial overrides coexist, creating contradictory tokens and hard-to-predict inheritance.
- Several labels are 7 to 10px, below the intended readability floor.
- Headings depend on condensed system fallbacks and can look compressed.
- The visual hierarchy relies too often on uppercase eyebrows.
- Some routes contain preview functionality that can look operational without sufficient qualification.
- Mobile tables, fixed navigation, and contextual panels require route-specific recomposition.
- Three.js remains visually useful but must be lazy, opt-in, and backed by a complete 2D fallback.

## 1. Brand & Voice
- Name: IDDRV.
- One-liner: industrial context, evidence, and human decisions in one local workspace.
- Voice: precise, technical, calm.
- Anti-patterns: generic SaaS cards, cyberpunk glow, marketing slogans, fabricated live state, fake financial certainty.

## 2. Visual System
- Palette source: `colors.csv`, CSV line 103, No. 102, “Inventory & Stock Management”.
- Exact colors: Primary `#334155`, On Primary `#FFFFFF`, Secondary `#475569`, On Secondary `#FFFFFF`, Accent `#059669`, On Accent `#FFFFFF`, Background `#F8FAFC`, Foreground `#0F172A`, Card `#FFFFFF`, Card Foreground `#0F172A`, Muted `#F2F3F4`, Muted Foreground `#64748B`, Border `#E6E8EA`, Destructive `#DC2626`, On Destructive `#FFFFFF`, Ring `#334155`.
- Typography source: `typography.csv`, CSV line 32, No. 31, “Financial Trust”.
- Heading font: IBM Plex Sans.
- Body font: IBM Plex Sans.
- Fonts will be packaged locally, not loaded from a CDN.
- DESIGN_VARIANCE: 4.
- MOTION_INTENSITY: 3.
- VISUAL_DENSITY: 8.

## 3. Stack
- Preserve React 18, Vite, TypeScript, React Router, TanStack Query, Three.js, and existing API contracts.
- Native CSS with semantic design tokens; no framework migration.
- Phosphor icons packaged locally for interface controls; custom SVG remains limited to data and spatial visualization.
- CSS transitions only for hover, focus, menu, and panel feedback.
- Three.js remains lazy-loaded behind `VITE_ENABLE_3D=true`.

## 4. Pages / Routes
- `/overview`: operational overview.
- `/sites`: multi-site scope.
- `/sites/:siteId/workshop`: 2D/3D workshop and replay.
- `/incidents`: incident queue.
- `/incidents/:incidentId`: evidence-backed investigation.
- `/workspace`: import preparation preview.
- `/imports`: import traceability.
- `/health`: local service administration.
- `/showroom`: explicitly fictitious guided demonstration.
- `/login`: pilot authentication.
- Existing opportunity route remains available and explicitly labeled as simulation.

## 5. Route composition

### Overview
Purpose: understand scope and priorities quickly.
Layout: metric ledger, site register, incident queue, provenance summary.
Motion: none beyond hover and focus.
Source: user dashboard references and Carbon grid discipline.

### Sites
Purpose: choose a physical perimeter.
Layout: single technical register with machine, incident, import, and status context.
Motion: row state only.

### Workshop
Purpose: locate a machine, inspect its state, and replay context.
Layout: spatial canvas, contextual inspector, temporal ruler.
Motion: direct camera manipulation and selection feedback only.
Source: user warehouse/digital-twin references.

### Incident queue
Purpose: prioritize persisted signals.
Layout: filter toolbar and dense table; mobile becomes labeled records.
Motion: row hover only.

### Incident detail
Purpose: move from symptom to evidence and feedback.
Layout: incident header, temporal reconstruction, hypothesis/evidence split, human verdict.
Motion: state changes only.

### Workspace and imports
Purpose: prepare metadata and inspect ingestion traceability without implying browser binary upload.
Layout: step-based work surface and audit table.
Motion: focus and progress feedback only.

### Health
Purpose: distinguish actual health response from expected contracts.
Layout: service state and neutral contract register.

### Showroom
Purpose: demonstrate the S001 story without contaminating operational truth.
Layout: spatial demonstration with a clearly marked fictitious inspector and provenance footer.

### Login
Purpose: resume the local pilot session.
Layout: split industrial field and focused form.

## 6. Animation inventory
- Hover/focus: 150ms ease-out on color, border, opacity, and transform.
- Press: 100ms translateY(1px).
- Mobile menu: 240ms opacity/transform if animated.
- Three.js: user-driven orbit/pan/zoom; no auto-rotation.
- No scroll reveals, pinned sections, parallax, or ambient loops.
- Reduced motion removes nonessential transitions.

## 7. MCP Research Log
- `search_tool_bm25("21st-dev ui-layouts chrome-devtools designmd")`: unavailable in this environment.
- `designmd("industrial operations dashboard")`: unavailable; retry `designmd("operations")`: unavailable.
- `ui-layouts("dense dashboard spatial inspector")`: unavailable; retry `ui-layouts("dashboard")`: unavailable.
- `21st-dev("industrial control room")`: unavailable; retry `21st-dev("dashboard")`: unavailable.
- `chrome-devtools`: unavailable as an MCP command.
- `web_search` and `browser`: unavailable as MCP commands.
- Fallback used: Python Playwright and direct network access.
- Carbon Design System captured at desktop/mobile; used for grid, shell, and density.
- IBM Design Language captured at desktop/mobile; used for spatial field and typography rhythm.
- Grafana captured at desktop/mobile; used as a contrast reference and to reject marketing patterns inside operational routes.
- Nine user screenshots remain the primary art-direction source.

## 8. Risks & Mitigations
- Existing CSS drift: consolidate to one token layer and remove dead cyber-theme values.
- Tiny labels: enforce 12px minimum for visible labels and 16px body text where content is explanatory.
- Mobile overflow: test every route at 375px and convert tables into labeled records.
- Tablet density: verify at 1024px, not only desktop/mobile.
- Three.js bundle: preserve lazy loading and validate both enabled/disabled builds.
- WebGL failure: preserve 2D path and visible mode control.
- Demo truthfulness: keep fictitious/preview labels adjacent to affected data.
- Unsupported backend claims: show unavailable/unknown rather than successful defaults.
- Font availability: package IBM Plex Sans locally through the frontend dependency graph.

## Batch execution
No approval wait. Implementation, browser review, correction cycles, and final verification follow immediately.
