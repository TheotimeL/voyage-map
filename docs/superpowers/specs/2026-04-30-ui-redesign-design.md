# Voyage Map — UI Redesign (map-first, dock + bottom sheet)

## Why

The current MapView has a 6-section vertical sidebar (Voyage header → Places → Itinerary → Routes → Daylight → Survival → Offline → Share footer). On desktop it forces scrolling; on mobile it collapses to a 50vh drawer that still scrolls and squeezes the map. The sidebar is the product's bottleneck.

User priorities (from brainstorming):
- **Both mobile and desktop matter equally** during the May 9–30 trip (planning + in-van).
- **High-frequency** sections: Places (now including trails), Itinerary — these stay one tap away.
- **On-demand** sections: Daylight, Survival POIs, Offline — these can be tucked behind a "More" affordance.

## Domain change: routes-as-points

The current data model has two top-level concepts: `Point` (a pin with title/comment/category) and `Track` (a GPX line with name/color but no notes/category/lat/lng). The user wants **routes to be first-class pinpoints with their own notes and metadata, just rendered differently on the map**. This means:

- A `Point` gains an optional `gpx_data` column (Text, nullable) and an optional `color` column (the existing track color, used only when `gpx_data` is set). When `gpx_data` is present, the point renders as a marker AT the trailhead (first GPX coordinate) PLUS a polyline AND an elevation profile when active.
- Trails get the same fields as any other point: `title`, `comment`, `category`, `lat`, `lng`. Categories are extended with a `trail` value, and the Places list distinguishes trail rows visually with a color swatch on the left edge.
- The dedicated "Routes" section disappears as a separate concept. Trails live in the Places list alongside campgrounds, viewpoints, water sources, etc.
- The existing `Track` table is migrated into `points` rows: each track becomes a Point with `category='trail'`, `lat`/`lng` set to the first GPX coordinate, `title` set to the track name, and `gpx_data` preserved. The `tracks` table and its API endpoints are removed.

## Approach: map-first + adaptive InfoPanel

The map fills the viewport at all times. A single component (`InfoPanel`) houses all controls and adapts its presentation to the viewport:

- **Mobile (≤ 720px):** bottom sheet, three drag-snap states (peek / half / full).
- **Desktop (> 720px):** floating dock anchored to the left, ~360px wide, collapsible to a thin icon rail.

A persistent "today's stop" banner overlays the top of the map (already exists — keep, light tweaks). The voyage title, coords, and radius slider are housed compactly inside InfoPanel, no longer above-the-fold.

## Layout

Tab structure becomes **two primary tabs** (Places, Itinerary) plus the ⋯ More menu — Routes is folded into Places.

### Mobile bottom sheet — three states
1. **Peek** (~64px above the safe-area inset): just the handle bar + tab bar. Map ≈ 95% of screen. The today's-stop banner remains a separate map overlay above this; it does not live inside the sheet.
2. **Half** (~50vh): the active tab's content. Default when a tab is tapped.
3. **Full** (~92vh): for deep editing (long itinerary, point form). Reached by drag-up or by tapping the active tab again.

Snap to nearest state on drag release. Tapping the map collapses to peek. Sheet content scrolls within the sheet — the handle stays sticky at top.

### Desktop floating dock
- Floats on the left, 360px wide, top-aligned with 16px inset on all sides.
- Internal header: voyage title (inline-edit), coords, radius slider — compact row.
- Tab bar: Places · Itinerary · ⋯
- Active tab content fills remaining height; overflow scrolls within the dock.
- Collapse button (⟨) collapses to a 48px icon rail (one icon per tab + ⋯). Click an icon to re-expand on that tab.

### Today's-stop banner
Already exists. Behavior unchanged: shown only when there *is* a "today" stop. Click → centers map + opens Itinerary tab in InfoPanel. On desktop, extend it with sunrise/sunset glance pulled from `useSun()` (so Daylight info bleeds into the most relevant context for free).

### Map overlays (always visible)
- Top-left: today's-stop banner (when applicable).
- Top-right: theme toggle + ⋯ map menu (settings).
- Bottom-right: locate-me button (existing) + new floating action button "Drop pin" (currently a `+ Drop` button buried in Places header).
- Bottom-left (desktop only): ElevationProfile overlay when an active track is selected (existing — unchanged).

## Tab content

### Places
Voyage title, coords, radius live in the dock's compact header (above tabs), not in this tab. Places tab itself contains:
- `GeocoderSearch`
- "Use my location" link
- `CategoryFilters` — gains a `trail` chip alongside the existing categories
- `PointList` — rows render trail-points with a color swatch, distance (km), and elevation gain (D+) inline; non-trail rows stay simple
- "Drop a .gpx anywhere on the map" hint stays in this tab as a footnote

The "+ Drop" button is removed from this tab — it becomes a map FAB. GPX import remains drag-and-drop on the map plus a `+ GPX` button in the Places tab header (next to the FAB-relocated drop-pin trigger).

### Itinerary
- `Itinerary` component as-is. No changes to its internals — only its container.

### ⋯ More menu
A popover (mobile: full-width modal sheet; desktop: anchored popover) containing:
- Daylight (`SunPanel`)
- Survival POIs (`SurvivalLayer`)
- Offline tiles (`PrecacheButton`)
- Share link (`Copy link`)
- Theme toggle (also accessible from map overlay)

## Component changes

### New
- `InfoPanel.vue` — adaptive container. Detects viewport via `matchMedia('(max-width: 720px)')`. Renders `<MobileSheet>` or `<DesktopDock>`. Owns the active-tab state.
- `MobileSheet.vue` — bottom sheet with drag-snap. Uses pointer events; snaps to peek/half/full. Emits `state` changes.
- `DesktopDock.vue` — fixed-position floating panel. Owns collapse-to-rail state.
- `TabBar.vue` — small tab bar component used by both. Props: `tabs`, `active`. Emits `update:active`.
- `MoreMenu.vue` — popover/sheet hosting Daylight, Survival, Offline, Share, Theme.
- `MapFab.vue` (or inline) — floating action button "Drop pin".

### Refactored
- `MapView.vue` — sheds its `<aside class="sidebar">` block. Renders `<InfoPanel>` + map overlays. Drops ~600 lines of sidebar CSS.
- The 6 section `<section class="sec">` wrappers and the `№ 0X` numbering disappear. Section identity is now carried by tabs/icons, not by numbered headings.

### Refactored (data-model unification)
- `services/models.py` — `Point` gains `gpx_data: Mapped[str | None]`. `Track` table is removed.
- `services/schemas.py` — `Point` schema gains optional `gpx_data` field. `Track` schema removed.
- `api/points.py` — accepts `gpx_data` on create/update.
- `api/tracks.py` — deleted.
- `api/maps.py` — stops nesting `tracks` in the map response; `points` carries everything.
- Migration: one-shot Python script that reads existing `tracks` rows, parses each GPX to extract first coordinate, inserts a `Point` with `category='trail'`, `lat`/`lng` = first coord, `title` = track name, `gpx_data` = original GPX, `comment` = null. Drops the `tracks` table afterward.
- `frontend/src/components/PointList.vue` — recognises trail rows (points with `gpx_data`) and renders a color swatch on the left edge. Click on a trail row toggles the polyline + elevation profile (replacing the current `activeTrackId` mechanism, which becomes `activeTrailPointId`).
- `frontend/src/components/CategoryFilters.vue` — adds a `trail` chip.
- `frontend/src/views/MapView.vue` — track-rendering logic (polyline, elevation profile, color swatch) keys off `point.gpx_data` instead of a separate `tracks` array. GPX drag-and-drop creates a `Point` with `category='trail'` and opens `PointFormModal` to edit name/notes.

### Untouched
- `Itinerary`, `SunPanel`, `SurvivalLayer`, `PrecacheButton`, `RadiusSlider`, `GeocoderSearch`, `PointDetailCard`, `PointFormModal`, `ElevationProfile`, `CompassRose`, `ThemeToggle` — all keep their public API. They become children of new containers (and `PointDetailCard` / `PointFormModal` already handle generic Point fields, so they accommodate trails for free).

## Visual language

Keep the vintage-travel-poster system intact (`vintage.css`):
- Cream paper, vermillion accents, Anton/Inter/JetBrains Mono.
- The InfoPanel is a "paper" surface (existing `.paper` class). Bottom sheet has a deckle-edge top border on mobile; dock has a 1px vermillion border with subtle drop shadow on desktop.
- Tab bar uses the existing `№ 0X` mono numbering as a left-aligned secondary label inside each tab's content header (so numbering survives, just not as section dividers).
- The dropped sidebar's deckle/major-rule motif moves to the dock's internal header divider.

## Interactions worth calling out

- **Click the today banner** while Itinerary tab is active and centered on today: pulse highlight on today's row (current behavior — keep).
- **Drop pin via FAB**: enters pin-drop mode (next click on map drops). Same behavior as current `startNewPin` — just relocated trigger.
- **Edit voyage title** stays an inline input in the dock header (mobile: in the sheet's full-state header).
- **Radius slider**: also in dock/sheet header. On mobile peek state, hidden; visible at half/full.
- **Collapse**: desktop dock collapse to icon rail is the only "hide UI" affordance — the bottom sheet always at least peeks. The current `sidebarOpen` toggle is replaced by this.

## Mobile-specific care

- Sheet drag must not fight Leaflet pinch-zoom: pointer events only on the handle bar and tab bar; content inside scrolls natively.
- Safe-area insets honored on iOS: sheet bottom respects `env(safe-area-inset-bottom)`.
- When a modal is open (`PointFormModal`), the sheet is hidden behind the modal backdrop — no double-layer scrolling.

## Build sequence

The migration ships incrementally; each step leaves the app working.

1. **Unify the data model.** Add `gpx_data` to `Point`, update schemas and API. Run the one-shot migration script that converts `tracks` rows into trail-points and drops the `tracks` table. Update `MapView.vue` to render trail-points (polyline + elevation) keyed off `point.gpx_data`. The "Routes" sidebar section now reads from points filtered by `gpx_data != null`. App still uses the old sidebar layout. Existing user data preserved.
2. **Scaffold InfoPanel + DesktopDock + TabBar.** Wire MapView to render them in parallel with the existing sidebar (behind a feature flag in dev). Two empty tabs (Places, Itinerary). No mobile yet.
3. **Migrate Places tab.** Move search, filters, list (with trail-row enrichment), and the existing `+ Drop` button into Places tab. Add `trail` filter chip. Move voyage header (title/coords/radius) to dock header. Sidebar still hosts everything else.
4. **Migrate Itinerary tab.** Sidebar now hosts only Daylight/Survival/Offline/Share.
5. **Build MoreMenu.** Migrate the remaining four into it. Sidebar deleted.
6. **Build MobileSheet + drag-snap.** InfoPanel switches based on viewport. Old `@media (max-width: 720px)` sidebar rules deleted.
7. **Move "Drop pin" to MapFab.** Remove `+ Drop` from Places header.
8. **Polish:** banner extension on desktop, collapsed icon rail, safe-area insets, transitions.

Each step is mergeable on its own. After step 6, the redesign is functionally done; steps 7–8 are polish.

## What we're explicitly NOT doing

- No new features. The user-facing scope is a layout/hierarchy redesign plus the routes-as-points unification — nothing else.
- Backend changes are limited to the `Point`/`Track` unification described above; no other API or schema work.
- No icon set overhaul; keep the existing emoji glyphs (📍 🗓 ☀ 💧 📡) for tabs/rail. Trail rows in PointList use a color swatch (existing track-color) plus a km / D+ summary, not an icon.
- No router/state-management refactor; tab state lives in InfoPanel local state.
- No animation library; CSS transitions + a small pointer-event drag handler are enough.

## Open questions

None. Decisions made unilaterally by Claude per the user's "go, choose everything" directive. The user will review this spec; any disagreements caught at that gate.
