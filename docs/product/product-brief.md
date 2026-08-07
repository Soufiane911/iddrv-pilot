# Cadrage produit IDDRV

## What it is
IDDRV is an on-premise industrial supervision and investigation application that reconciles ERP, machine, quality, maintenance, and operator data to locate incidents and expose supporting evidence.

## Target audience
- Production operators and team leads monitoring machine state.
- Quality and methods specialists investigating process drift.
- Production managers prioritizing incidents and follow-up actions.
- Supervisors validating decisions.
- Administrators managing local services, sites, users, and imports.

## Primary job-to-be-done
Move from a workshop signal to its machine context, historical window, hypotheses, and persisted evidence without losing site or time context.

## Brand voice
Precise, technical, calm.

## Key messages
- Every operational value needs a time window and source.
- The workshop is a spatial entry point into investigations.
- The deterministic engine proposes explanations; a human remains responsible for decisions.

## Anti-references
- Not a generic SaaS card dashboard.
- Not cyberpunk, glassmorphic, or neon-heavy.
- Not a marketing site disguised as an operations product.
- Not a fake live-control interface.

## User-provided facts
- Source: user: Redesign the entire existing frontend at senior art-direction quality.
- Source: user: Preserve backend, routes, functionality, real data, and existing contracts.
- Source: user: The supplied monochrome dashboards and spatial industrial interfaces are visual references.
- Source: user: The Three.js workshop should remain a virtual machine-park view with navigation and interaction.
- Source: user: Work in Batch mode without questions or approval waits.

## Missing facts
- Exact customer brand guidelines: [NEEDS INPUT]
- Field-tested target hardware and browser matrix: [NEEDS INPUT]
- Licensed corporate typeface or logo assets: [NEEDS INPUT]
- Real industrial export validation status: [NEEDS INPUT]

## Working assumptions
- Desktop control-room and office use are primary; tablet and mobile remain fully usable.
- Light monochrome surfaces support dense analytical work; the workshop may use a spatial field.
- No CDN dependency is acceptable for the on-premise pilot.
- Production routes use the backend’s HttpOnly cookie session; local Vite development may remain ungated for visual work.

## Constraints
- WCAG 2.2 AA target.
- No invented metrics, savings, customers, claims, or machine-control capability.
- 2D remains a complete fallback; Three.js remains opt-in.
- Runtime must not read evaluation-only ground truth.
- Approval required before build: no, Batch mode.
