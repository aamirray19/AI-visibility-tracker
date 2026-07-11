
# BrandSightAI — minimal landing rebrand

Replace the current AssetWise IT asset tracker with a single, focused BrandSightAI landing page. The page's only interactive element is a text box where the user enters a domain (e.g. a CRM product name like "Salesforce", "HubSpot"). Everything else from the old app is removed from the user-facing surface.

## What the page contains

- BrandSightAI logo + wordmark (top left)
- Hero headline + one-line subhead positioning it as an AI brand monitoring platform
- A single large input: "Enter a brand or domain to monitor" with a "Track brand" button
- A small helper line under the input (e.g. "Try: Salesforce, HubSpot, Notion")
- Subtle footer with copyright

No nav links, no dashboard preview, no feature grid, no login/signup, no asset/employee/AI-chat pages.

For now, submitting the input shows a toast like "Tracking {domain} — we'll notify you when monitoring is ready." No backend wiring; this is a waitlist-style capture. (We can wire it to Lovable Cloud later if you want.)

## Visual direction (black & purple)

- Background: near-black `oklch(0.12 0.02 280)` with a soft radial purple glow behind the hero
- Primary purple accent: `#A855F7` (vivid) with a deeper `#6D28D9` for gradients
- Text: off-white on dark; muted lavender for secondary text
- Typography: Space Grotesk (display) + Inter (body), loaded via `<link>` in `__root.tsx`
- Input: dark surface, purple focus ring, glowing border on hover
- Subtle grain/noise overlay on the background for depth

## Files to change

- `src/routes/index.tsx` — replace landing entirely with new BrandSightAI hero + input
- `src/components/landing-page.tsx` — replace with the new minimal component (or inline into the route)
- `src/styles.css` — add black/purple tokens, gradient + glow variables
- `src/routes/__root.tsx` — update site title to "BrandSightAI", update meta description, add Space Grotesk + Inter `<link>` tags
- Delete (no longer reachable from the UI; safe to remove from routes):
  - `src/routes/assets.index.tsx`, `assets.new.tsx`, `assets.$assetId.tsx`, `assets.$assetId.edit.tsx`
  - `src/routes/employees.tsx`, `settings.tsx`, `ai-chat.tsx`, `reset-password.tsx`
  - `src/components/landing-demo-dashboard.tsx`, `dashboard-view.tsx`, `assets-list-view.tsx`, `asset-detail-view.tsx`, `asset-form-view.tsx`, `employees-list-view.tsx`, `settings-view.tsx`, `login-page.tsx`, `app-layout.tsx`

Backend (Supabase tables, edge functions, auth) stays in place but unused — leaving it intact so we can wire the input to it later without re-doing migrations.

## Out of scope (ask if you want any of these next)

- Persisting submitted domains to the database
- Auth / waitlist email capture
- Showing a list of tracked brands or any monitoring results
