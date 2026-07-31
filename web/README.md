# /web — Frontend

Next.js App Router site that displays predictions from the Go API. Built to render almost entirely on the server — there is currently **zero client-side JavaScript** for interactivity (no `'use client'` components anywhere yet).

## Important: this is a newer Next.js than you might expect

This project uses Next.js 16 / React 19, which changed some fundamentals from earlier versions — most relevantly, `params` and `searchParams` in page components are now **Promises** that must be `await`ed, not plain objects. `web/AGENTS.md` (auto-loaded via `web/CLAUDE.md`) flags this and points at `node_modules/next/dist/docs/` for the current docs — worth reading if something looks different from a Next.js tutorial you've seen before.

## How a page works, end to end

Take `app/predictions/page.tsx` as the representative example:

1. It's an `async function` Server Component — the whole component runs on the server, never ships to the browser as JS.
2. `searchParams` (a `Promise<{season?, gameweek?, position?, team?}>`) is awaited to read the URL's query string — e.g. `/predictions?gameweek=5&position=MID`.
3. `lib/api-client.ts` functions (`getCurrentGameweek`, `getPredictions`) are called directly, `await`ed, inside a `try`/`catch`. If the Go API is unreachable or returns an error, the `catch` branch returns an `<ErrorNotice>` early — the rest of the function (and its JSX) never runs.
4. The success path builds a `<form action="/predictions">` (a plain HTML GET form — no `onSubmit` handler, no client JS) whose fields are pre-filled with the current filter values via `defaultValue`. Submitting it just navigates to a new URL with different query params, which re-runs this whole Server Component with the new `searchParams`. Filtering is just "load a different URL" — no client state at all.
5. `<PredictionsTable>` renders the results as a plain `<table>`.

Every other data page (`app/page.tsx`, `app/fixtures/page.tsx`, `app/players/[id]/page.tsx`) follows the identical shape.

## The `try`/`catch` JSX split (a mid-build fix)

Early versions of these pages built the success-path JSX *inside* the `try` block, on the theory that a render error would also be caught. ESLint's `react-hooks/error-boundaries` rule flagged this as wrong: React doesn't render JSX synchronously when it's constructed, so a `try` around JSX construction doesn't actually protect against render errors — only against errors thrown by the plain `await` calls before it. The fix (now the pattern in every page) is: do all the `await`ing inside `try`/`catch`, assign results to `let` variables declared outside it, `return` the error JSX from inside `catch`, and only build the success JSX in a `return` *after* the `try`/`catch` block entirely.

## Why fetches aren't cached

Next.js 16 introduced a new caching model ("Cache Components", opt-in via `cacheComponents: true` in `next.config.ts` — **not enabled** in this project) built around a `'use cache'` directive. Without opting in, `fetch()` inside a Server Component is simply uncached by default — every request re-fetches from the Go API. That's the right behavior for this project's first version: predictions/fixtures only change weekly, but correctness (always showing the latest DB state) mattered more than shaving latency for a v1. Caching is a reasonable thing to revisit later; see the root plan's "open items" for this exact note.

## Predicted vs. actual points

`PredictionsTable` (`components/PredictionsTable.tsx`) shows two extra columns — "Actual points" and "Difference" — but only when the data actually has them: `hasActuals = predictions.some(p => p.actual_points !== null)`. For a future gameweek (nothing played yet), `actual_points` is `null` for every row and the table just shows predictions, same as before this feature existed. For a backtest/historical gameweek (see `ml/README.md`'s backtest section), every row has a real `actual_points` from the API, and the extra columns appear automatically — nothing page-level had to change, since `app/predictions/page.tsx` already lets you pick any `season`/`gameweek` via the filter form, e.g. `/predictions?season=2025-26&gameweek=1`.

## Judgment calls worth knowing about

- **`API_BASE_URL` is a server-only env var** (see `.env.example`) — deliberately *not* prefixed `NEXT_PUBLIC_`, so it's only readable in server-side code and never reaches the browser bundle. This is a direct consequence of every fetch happening in a Server Component; a fully client-rendered app would need the public prefix.
- **`lib/api-client.ts` narrows `unknown` rather than casting** — the raw `fetch().json()` result is typed `unknown`, checked with a type guard (`isEnvelope`) before being trusted, per the project's "no `any`" convention.
- **No SWR/React Query/tRPC.** Those libraries solve client-side data fetching and caching — this app deliberately fetches everything server-side, so they'd add bundle weight for a problem this app doesn't have.
- **Tailwind CSS, no CSS-in-JS.** Tailwind compiles to static CSS with no client-JS runtime cost and has no known friction with Server Components, unlike some CSS-in-JS libraries.

## Where to look

- `lib/api-client.ts` — the one place that talks to the Go API; also where the envelope-narrowing logic lives.
- `types/api.ts` — hand-written types mirroring the Go API's JSON shapes (not code-generated — the endpoint count doesn't justify an OpenAPI toolchain yet).
- `components/` — small presentational pieces shared across pages (`PredictionsTable`, `FixturesTable`, `ErrorNotice`, `Nav`). None of them are Client Components.
- `app/predictions/page.tsx` — the most fully-featured page (filters via a GET form); good template for any new filtered-list page.

## Running it

```
cp .env.example .env.local   # set API_BASE_URL to wherever the Go API is running
npm run dev
npm run lint
npx tsc --noEmit
```
