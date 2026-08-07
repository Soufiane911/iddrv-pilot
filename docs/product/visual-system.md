# Système visuel IDDRV

## Brand
- Name: IDDRV
- Voice: precise, technical, calm
- Art direction: an industrial evidence ledger wrapped around a spatial workshop instrument
- Anti-patterns: cyberpunk glow, glass cards, decorative gradients, oversized marketing heroes, inactive controls, unsupported live-state claims

## Color System
Source: `colors.csv`, CSV line 103, No. 102, Inventory & Stock Management.

- Primary: `#334155`, navigation emphasis and primary controls
- On Primary: `#FFFFFF`
- Secondary: `#475569`, watch and secondary state
- On Secondary: `#FFFFFF`
- Accent: `#059669`, selection, confirmed state, active focus
- On Accent: `#FFFFFF`
- Background: `#F8FAFC`, application field
- Foreground: `#0F172A`, primary text
- Card: `#FFFFFF`, panels and work surfaces
- Card Foreground: `#0F172A`
- Muted: `#F2F3F4`, quiet rows and grouped controls
- Muted Foreground: `#64748B`, secondary text
- Border: `#E6E8EA`, rules and separators
- Destructive: `#DC2626`, critical incident and error
- On Destructive: `#FFFFFF`
- Ring: `#334155`, keyboard focus

Dark spatial field, derived only from the same row:
- Background: `#0F172A`
- Foreground: `#F8FAFC`
- Card: `#334155`
- Card Foreground: `#FFFFFF`
- Muted: `#475569`
- Muted Foreground: `#E6E8EA`
- Border: `#475569`
- Accent and Ring remain `#059669` and `#334155`

Allowed derivations:
- Alpha and `color-mix()` variants may use only the palette colors above.
- Three.js geometry materials derive from Primary, Secondary, Accent, Background, Card, Border, and Foreground.
- No additional visible hex colors.

## Typography
Source: `typography.csv`, CSV line 32, No. 31, Financial Trust.

- Heading Font: IBM Plex Sans
- Body Font: IBM Plex Sans
- Delivery: locally packaged through `@fontsource/ibm-plex-sans`; no CDN
- Display: IBM Plex Sans 650, up to 56px, -0.03em, 1.06; showroom hero only
- Page title: IBM Plex Sans 650, up to 40px, -0.025em, 1.1
- Shell title: IBM Plex Sans 650, 20px, -0.015em, 1.15
- Section title: IBM Plex Sans 650, 20px, -0.012em, 1.2
- H3: IBM Plex Sans 600, 18px, -0.01em, 1.3
- Body: IBM Plex Sans 400, 16px, 0, 1.55
- Small: IBM Plex Sans 400, 14px, 0, 1.45
- Caption: IBM Plex Sans 500, 12px, 0.03em, 1.35
- Data: IBM Plex Sans 600 with tabular figures, 14px, 0, 1.3
- Type scale ratio: 1.2
- Maximum prose length: 68ch
- Uppercase labels: reserved for table headers, state categories, and compact metadata; never above every section

## Spacing
- Base unit: 4px
- Scale: 4, 8, 12, 16, 24, 32, 48, 64
- Page padding: 16px mobile, 32px tablet, 40px desktop
- Section rhythm: 24px dense, 32px standard, 48px major
- Component gap: 12px or 16px
- Control height: 44px minimum
- Content maximum: 1480px

## Grid
- Desktop application shell: 224px navigation plus fluid content
- Page grid: 12 columns, 16px gutters
- Workshop: 64px tools, fluid scene, 300px inspector
- Breakpoints: 640px, 768px, 1024px, 1280px, 1536px
- Tablet at 1024px is a first-class composition, not a desktop shrink
- Mobile stacks context panels and converts wide tables into labeled records

## Radius
- Cards: 2px
- Buttons: 2px
- Inputs: 2px
- Badges: 2px
- Popovers and menus: 2px
- Circular exception: status dots, chart rings, and compass only

## Borders and Elevation
- Level 0: no shadow; use Border rules
- Level 1: `0 4px 16px color-mix(in srgb, #334155 10%, transparent)` for menus only
- Level 2: `0 16px 40px color-mix(in srgb, #334155 16%, transparent)` for modal sheets only
- No shadow on routine cards, tables, or metrics

## Motion
- Hover: 150ms ease-out, color/border/opacity/transform
- Press: 100ms ease-out, translateY(1px)
- Menu entrance: 240ms cubic-bezier(.23,1,.32,1), opacity and translateY(4px)
- Menu exit: 160ms ease-in
- Scene camera: direct user input with damping; no autoplay
- No scroll reveal, parallax, bounce, or infinite decorative animation
- Reduced motion: transitions and CSS animations reduced to 0s; camera remains direct-input only

## Component Patterns
- Shell: light technical rail, persistent desktop navigation, five-item mobile dock with a functional More menu
- Page header: one title, one contextual sentence, optional action; eyebrow used only when it adds operational category
- Metrics: flat ledger cells separated by rules
- Sites: technical register rather than a card grid
- Tables: dense desktop rows; labeled mobile records
- Workshop: spatial field plus inspector plus temporal ruler
- Evidence: source, observed value, baseline, delta, and period remain grouped
- State panels: icon, state title, recovery instruction, optional action
- Forms: visible labels, helper/error below, 44px controls, focus-within on composite inputs
- Demo surfaces: fictitious status visible adjacent to the affected content

## Image and Spatial Style
- No stock photography and no remote image CDN
- The Three.js workshop and SVG plan are the product-specific visual assets
- Scene: credible industrial volumes with shared chamfered geometry, restrained palette, local high-bay lighting, soft contact shadows, and procedural concrete variation; no neon
- Materials: palette-derived painted steel, brushed metal, rubber, translucent guarding, and neutral roughness/bump maps generated locally; no remote texture or HDRI
- Camera and render: perspective inspection view, ACES tone mapping, sRGB output, soft shadows, demand-driven frames, and locally generated reflection forms
- Overlays: machine labels may be hidden for inspection; selected machines, reconstructed anomalies, keyboard controls, and status colors remain available
- Showroom: technical 2.5D reconstruction, visibly marked fictitious

## Accessibility
- WCAG 2.2 AA target
- Body text 16px minimum; persistent labels 12px minimum
- Focus indicators visible on every interactive element
- Touch targets 44x44px minimum
- Status never communicated by color alone
- Semantic landmarks and logical heading order
- Full keyboard operation for navigation, tables, machine selection, replay, forms, and menus
- `prefers-reduced-motion` respected globally
- No horizontal page overflow at 375px, 1024px, or 1440px
