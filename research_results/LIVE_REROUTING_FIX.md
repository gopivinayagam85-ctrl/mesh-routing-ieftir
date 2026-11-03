# Live Before/After Rerouting Fix

The rerouting panel now uses two real backend steps:

1. **Inject failure** sends `/api/reroute` with `repair: false`. The backend removes the selected node, removes affected active links, invalidates routes through the failed node, and returns the failed topology without computing a replacement route.
2. **Run IEFT-IR Rerouting** sends the same selected source and failed node with `repair: true`. The backend computes replacement paths and returns measured repair timing and route-update counts.

The before and after graphs use the same topology coordinates. Failed nodes and links are shown only after a failure is actually injected. Existing callers that omit `repair` retain the previous default behavior (`repair: true`).

## Verification

- Backend test suite: **88 passed**.
- Frontend JSX syntax parse: passed.
- A production Vite build could not be completed in the Linux validation environment because the bundled `node_modules` from the supplied archive does not contain Rollup's Linux optional native package. This is an environment/dependency issue; no frontend build success is claimed. On the target machine, install dependencies from `frontend/package-lock.json` and run `npm run build`.

## Run locally

Start the backend from `backend/` using the project's existing setup, then start the frontend from `frontend/` with `npm run dev`.
