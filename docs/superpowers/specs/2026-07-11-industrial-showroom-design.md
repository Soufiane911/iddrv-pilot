# IDDRV Industrial Showroom Design

## Goal

Transform the current site-list landing experience into an interactive commercial showroom where a prospect immediately recognizes a virtual production workshop, follows an evidence-backed incident investigation, and understands how IDDRV can turn industrial data into proposed actions and measurable value.

The first version uses the existing fictitious industrial dataset. It is a transparent demonstration, not a claim that OPC UA or financial savings validation are already production-ready.

## Scope

This phase delivers one polished vertical slice:

1. enter a generated hybrid isometric workshop;
2. start or skip a guided commercial tour;
3. focus on machine 606 when its incident appears;
4. inspect machine context and diagnostic evidence;
5. view a proposed improvement action;
6. inspect a transparent demonstration-only impact estimate;
7. leave the tour at any time and explore freely.

The existing operational pages remain available. This phase does not implement a real OPC UA connector, real browser file ingestion, a production financial model, machine control, or a complete action-management backend.

## Product principles

- **Spatial before tabular:** the workshop is the home screen and primary navigation surface.
- **Recognizable, not photorealistic:** layout is faithful enough to resemble a customer site while machines use a consistent stylized visual language.
- **Evidence before recommendation:** every diagnostic claim exposes its source, observed value, baseline, delta, and time window.
- **Human authority:** the system proposes; authorized humans approve, reject, assign, or request verification.
- **Progressive disclosure:** all users can understand the overview, while deeper evidence and controls appear on demand.
- **Truthful demonstration:** fictitious data, simulated time, unavailable connectors, and estimated impact are labeled explicitly.
- **Operational fallback:** the existing 2D map remains available and functionally complete when isometric rendering is disabled or unsuitable.

## Target users and permissions

The information architecture is shared across roles instead of creating separate products.

| Role | Primary needs | Allowed interaction in the showroom phase |
|---|---|---|
| Operator / team lead | Understand workshop state and add context | View, navigate, inspect, comment |
| Quality / methods | Investigate causes and qualify evidence | View, investigate, confirm/reject hypothesis |
| Production manager | Prioritize recommendations | View, compare, propose or assign follow-up |
| Supervisor / industrial management | Control decisions and value claims | Approve/reject actions and configured assumptions |
| Administrator | Configure sources, sites and permissions | Access data and administration areas |

Buttons that require a higher role remain understandable. They are disabled or replaced with a clear explanation rather than disappearing silently.

## Experience architecture

```text
Industrial group
  -> Site
    -> Isometric workshop
      -> Zone or production line
        -> Machine
          -> Incident
            -> Evidence and hypotheses
              -> Proposed action
                -> Estimated then validated impact
```

The global navigation becomes:

- Workshop
- Incidents
- Actions
- Impact
- Data
- Administration

Health and connection diagnostics move under Administration. The first showroom phase may link Actions and Administration to existing or explicitly labeled preview states rather than pretending full workflows exist.

## Home screen composition

Desktop uses a three-part command-center layout:

1. a compact persistent navigation rail;
2. the workshop canvas occupying most of the screen;
3. a contextual inspector that opens for the selected site, machine, incident, evidence item, or action.

A replay/tour rail sits at the bottom of the workshop. It contains the current simulated timestamp, tour progress, play/pause, previous/next steps, and an exit-tour action.

Small screens use the 2D map by default. Context opens as a bottom sheet. Isometric rendering must never be required to reach core information.

## Workshop representation

The default workshop is a hybrid isometric 2.5D scene generated from the existing machines and layout coordinates. It includes:

- zones, circulation paths, machines, quality area and contextual labels;
- machine state expressed by icon, label and color;
- selected-machine outline and subtle elevation;
- incident marker anchored to the affected machine;
- pan, zoom, reset-view and fit-workshop controls;
- a visible switch between isometric and technical 2D views.

The style borrows spatial clarity from management games, not their reward mechanics. No coins, artificial scores, celebratory effects, cartoon alarms, or game-like treatment of safety events are used.

Motion is short, interruptible and functional. Reduced-motion disables camera interpolation, pulses and decorative transitions.

## Guided story

The existing S001 scenario becomes a seven-step tour:

1. **Workshop reconstructed:** explain that ERP, machine, quality, maintenance and operator-note sources were combined.
2. **Stable production:** establish a healthy comparison period.
3. **Drift detected:** machine 606 changes from stable to watch, then incident state.
4. **Impact observed:** scrap and cycle indicators worsen at the same simulated period.
5. **Investigation completed:** show the evidence-backed zone-2 thermal drift hypothesis and alternatives.
6. **Action proposed:** recommend a verification step before the next comparable production order.
7. **Impact estimated:** show an explicitly simulated range with editable assumptions and formulas.

Each step contains one short headline, one sentence of explanation and one primary action. The user can pause, go backward, skip, or switch to free exploration without losing the selected machine and timestamp.

## Machine inspector

Selecting a machine opens an inspector with:

- machine name, state and current production order;
- TRS, scrap rate and cycle-time variance;
- selected simulated timestamp and source freshness;
- recent incident count;
- actions: Understand incident, View signals, View history.

Every value indicates whether it belongs to the selected historical timestamp, an aggregate interval, or the latest available record. Static values must not appear to replay when they do not change with time.

## Investigation inspector

The investigation view shows:

- ranked hypotheses, not only the first one;
- confidence as supporting context rather than proof;
- supporting and contradicting evidence;
- missing data and the next recommended check;
- synchronized traces for zone temperature, scrap and cycle time;
- incident and healthy-baseline windows;
- evidence drill-down with source, file or node provenance, timestamp, observed value, baseline and delta.

The first phase may derive the traces from existing deterministic scenario data, but it must label the selected period and preserve the runtime prohibition against reading evaluation-only ground truth.

## Proposed action

The commercial vertical slice represents an action proposal with:

- recommendation;
- evidence-based justification;
- operational risk;
- recommended responsible role;
- estimated duration;
- success metric;
- approval status.

Only authorized roles receive active approval controls. If the existing backend action contract is not extended during this phase, the showroom action remains explicitly labeled as a demonstration preview and does not claim persistence.

## Economic impact

No hard-coded incident amount may be presented as evidence-derived savings.

The demonstration uses visible assumptions such as material cost, scrap quantity, machine-hour cost and recoverable time. It shows the formula and labels the result:

> Demonstration estimate based on configured fictitious costs.

The UI distinguishes:

- potential impact;
- approved estimate;
- realized and validated impact.

Only the first is populated in this phase unless a real measurement workflow exists.

## Data and OPC UA messaging

The data area distinguishes capability states:

- file-based batch ingestion: available where backed by the current worker;
- watched-folder automatic ingestion: available;
- browser upload: unavailable until actual file bytes are transferred;
- OPC UA: roadmap preview until a real connector, security configuration, subscriptions, reconnection, buffering and provenance are implemented.

The showroom may display an OPC UA connection concept, but it must be marked Preview and must not display a false connected state.

## Visual system

- Light industrial surface with deep-navy navigation.
- One turquoise accent for navigation and selection.
- Amber for watch states; red only for critical incidents.
- Status is never communicated by color alone.
- One consistent SVG icon family; no emoji icons.
- Locally hosted fonts or system font stack to preserve offline/on-prem operation.
- Tabular figures for measurements, durations and currency.
- Visible focus states and 44-pixel minimum interactive targets.
- Animation duration generally 150-300 ms and fully compatible with reduced motion.

## States and failure handling

The showroom defines explicit states for:

- loading workshop geometry and machine data;
- no machines imported;
- partial source coverage;
- stale or unavailable data;
- replay unavailable;
- investigation not yet run;
- insufficient evidence / abstention;
- failed investigation with retry;
- isometric renderer unavailable, with automatic 2D fallback;
- restricted action due to role;
- demonstration-only or preview feature.

The static local-environment indicator is replaced by actual freshness and service-health information or by neutral wording that does not imply connectivity.

## Accessibility and responsive behavior

- Every machine is keyboard reachable in isometric and 2D views.
- A textual machine list mirrors all spatial interactions.
- Focus moves to the contextual inspector after explicit machine activation and returns predictably on close.
- Charts provide textual summaries and table alternatives.
- Tour changes use polite live-region announcements.
- Isometric controls have labels and do not rely on drag gestures alone.
- Mobile and reduced-capability devices default to the 2D representation.
- The application preserves zoom and avoids nested scroll regions around the main canvas.

## Technical boundaries

The first implementation remains in the existing React/Vite application and reuses the current API and fictitious scenario. The isometric renderer is an isolated, lazy-loaded frontend module. The operational 2D workshop and current routes remain available throughout migration.

The phase must not:

- add an OpenAI runtime dependency to the IDDRV application;
- read `data/scenarios/industrial_demo/ground_truth.json` at runtime;
- claim that OPC UA is connected;
- invent evidence-backed monetary values;
- remove existing authentication, RBAC, multi-site isolation or replay safeguards.

## Verification

Acceptance requires:

1. desktop guided-tour smoke from workshop entry through impact estimate;
2. free-exploration smoke with machine selection and 2D fallback;
3. keyboard-only navigation through workshop, inspector and tour controls;
4. reduced-motion verification;
5. mobile viewport verification at 375 px;
6. explicit demo/preview labels for fictitious costs and OPC UA;
7. frontend lint, tests and production build;
8. no runtime access to evaluation-only ground truth;
9. no regression to existing incident and workshop routes.

## Delivery sequence

1. Build a local interactive showroom prototype using the fictitious dataset and no backend changes.
2. Validate the spatial layout, guided story and inspector behavior with users.
3. Integrate the accepted experience into the application behind a feature flag.
4. Replace demonstration-only action and impact states with persisted workflows in later phases.
5. Add OPC UA only after a real connector is field-tested.
