# RC3 Talent Intelligence - Frontend

Next.js 16 (App Router) + TypeScript + Tailwind v4 + shadcn/ui (Radix) + TanStack Query/Table.

- `npm install && npm run dev` (port 3000). All calls go to same-origin `/api/*`, rewritten to `API_URL` (default `http://localhost:8000`).
- Rewrite destinations are baked in at build time: `docker build --build-arg API_URL=http://api:8000 .`
- Auth is a cookie (`ats_session`) set by the API; route guards are client-side (`GET /api/auth/me`). There is intentionally no `proxy.ts`/middleware so large uploads are streamed straight through the rewrite.
- Checks: `npm run build` (type-check) and `npx eslint src`.
