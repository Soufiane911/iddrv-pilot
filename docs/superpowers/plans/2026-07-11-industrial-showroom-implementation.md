# Industrial Showroom Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a testable commercial showroom that opens on a hybrid isometric workshop and guides users through the fictitious machine-606 incident, evidence, action proposal, and transparent simulated impact.

**Architecture:** Add a dedicated `/showroom` React page that consumes the existing API boundary and keeps all commercial-story data in a typed frontend presentation model. Render the workshop with accessible DOM/CSS isometric tiles so it remains fast and testable, while preserving the existing `/sites/:siteId/workshop` 2D/3D operational route. The existing backend, ingestion runtime, diagnostic engine, and evaluation-only files remain untouched.

**Tech Stack:** React 18, TypeScript, React Router, TanStack Query, CSS, Vitest, Testing Library.

---

### Task 1: Showroom presentation model and tests

**Files:**
- Create: `frontend/src/features/showroom/showroomModel.ts`
- Create: `frontend/src/test/showroom.test.tsx`

- [ ] Define the seven guided-tour steps, fictitious cost assumptions, formula-based impact estimate, and helper functions for step navigation and machine state.
- [ ] Add a test asserting the visible demo label, machine 606 incident state, tour navigation, evidence, action proposal, and formula disclosure.
- [ ] Run `npm --prefix frontend run test` and confirm the new test fails before the page exists.

### Task 2: Accessible hybrid workshop components

**Files:**
- Create: `frontend/src/features/showroom/ShowroomWorkshop.tsx`
- Create: `frontend/src/features/showroom/ShowroomInspector.tsx`
- Create: `frontend/src/features/showroom/ShowroomTour.tsx`

- [ ] Implement a keyboard-accessible isometric DOM scene using existing machine layout coordinates and semantic buttons.
- [ ] Implement machine, investigation, action, and impact inspector states with visible provenance and simulation labels.
- [ ] Implement guided-tour controls with start, pause, previous, next, exit, and polite announcements.
- [ ] Keep every spatial action mirrored by an accessible machine list.

### Task 3: Showroom page and routing

**Files:**
- Create: `frontend/src/pages/ShowroomPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

- [ ] Fetch the first available site, its machines and incidents through the existing `ApiClient`.
- [ ] Route `/` and unknown paths to `/showroom`, while preserving all existing routes.
- [ ] Make Workshop the first navigation item and update labels to Workshop, Incidents, Actions, Impact, Data, Administration without claiming unavailable workflows.
- [ ] Suppress the standard page topbar only for the immersive showroom and expose neutral demo/freshness wording.

### Task 4: Visual system, responsive behavior and motion safety

**Files:**
- Create: `frontend/src/features/showroom/showroom.css`
- Modify: `frontend/src/components/layout.css`
- Modify: `frontend/src/styles.css`

- [ ] Build the navy/slate/turquoise command-center layout with an isometric 2.5D workshop, contextual inspector and bottom tour rail.
- [ ] Add explicit stable/watch/incident states using text and icons in addition to color.
- [ ] Add a 2D/list fallback at 780 px and a contextual bottom-sheet layout at 375 px.
- [ ] Respect `prefers-reduced-motion`, visible focus states, 44-pixel targets and system/local fonts.

### Task 5: Verification and review

**Files:**
- Modify as required only within `frontend/` based on verified findings.

- [ ] Run `npm --prefix frontend run lint`.
- [ ] Run `npm --prefix frontend run test`.
- [ ] Run `npm --prefix frontend run build`.
- [ ] Run a Playwright desktop smoke of the guided path and capture a screenshot.
- [ ] Run a 375-pixel smoke and verify the fallback remains usable.
- [ ] Search runtime frontend code to confirm it does not access `ground_truth.json` and does not claim OPC UA is connected.
- [ ] Request a read-only review focused on misleading claims, accessibility, responsive behavior and regression risk.

## Self-review

- The plan implements the approved commercial vertical slice without backend or evaluation-data changes.
- Existing operational routes and the technical 2D map remain intact.
- Economic impact is formula-based and explicitly fictitious.
- OPC UA remains a labeled preview, not a connected state.
- Every new UI state has a verification step and no placeholder content is required.
