# Domi frontend

Next.js 16 (App Router) + TypeScript + Tailwind 4, with Leaflet / OpenStreetMap, Phosphor icons and Motion.
Every page calls the real backend (`/api/listings`, `/api/cities`, `/api/chat` over SSE, `/api/compare`,
`/api/mortgage/*`). There is no mock data: if the backend is down, pages show an error state with a retry.

## Run it

```
# terminal 1: backend (from backend/)
.venv\Scripts\python run.py            # http://localhost:8000

# terminal 2: frontend (from frontend/)
copy .env.local.example .env.local     # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                            # http://localhost:3000
```

Checks: `npm run lint`, `npx tsc --noEmit`, `npm run build`.

## Pages

| Route | What it is |
|---|---|
| `/` | Landing: hero search, bento features, how it works, city cards (live stats), closing banner |
| `/explore` | Filters (one row), list and Leaflet map 50/50, price pins. "Ask Domi" is a widget: closed by default, opens as a side panel and the map compresses. `?view=grid` is the grid-only view |
| `/listings/[id]` | Detail: location views, facts, live monthly estimate, "Ask Domi about this home" |
| `/compare?id=...&id=...` | 2-3 homes as aligned cards, best-value cells, tool-derived tradeoffs, shared payment assumptions, same collapsible Ask Domi widget |
| `/affordability` | Mortgage calculator, 15 vs 30 year comparison, "how much could I afford". No Ask Domi on this page, by design |

## Notes

- **No listing photos.** The RentCast data has none, so cards show a real OpenStreetMap view of each
  home's coordinates (zoomed closer for condos and multi-family, with a house / building / tree pin by
  property type). To show distinct photos, add image files to `public/home-photos/` and list them in
  `manifest.json`: each listing gets one from the pool by a stable hash of its id (see that folder's
  README). Pool photos are not photos of the listed home, so label them illustrative.
- **Answers are structured.** Domi's replies are a one-sentence lead-in plus short bullets, and the
  homes appear as cards below (`components/chat/RichText.tsx` renders `- ` / `+ ` / `1. ` lines).
- **Map tiles** come from `tile.openstreetmap.org`, fine for development and light use. Use a hosted
  tile provider before real traffic (see OSM's tile usage policy).
- **Chat <-> page sync.** The page sends its current filters and selected homes with each chat
  message; Domi's search results update the filter bar, list and map pins.
- **Motion.** Entrance effects are CSS (visible without JS, honour `prefers-reduced-motion`);
  Motion is used for chat and drawer transitions. `NEXT_PUBLIC_DISABLE_MOTION=1` turns those off
  (used for automated browser checks, where background windows never run animation frames).
- Dark mode follows the system setting; set `data-theme="light"` or `"dark"` on `<html>` to force one.
