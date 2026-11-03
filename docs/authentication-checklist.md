# Public-demo authentication checklist

This file tracks the acceptance gates from the authentication completion plan.

- [x] A0 — Existing backend/frontend baseline recorded before changes.
- [x] A1 — Team credentials removed from YAML and validated from `TEAM_API_KEYS_JSON`.
- [x] A2 — Bearer parsing, timing-safe comparison, standard `401`, and no downstream work after rejection.
- [x] A3 — Sanitized, side-effect-free `GET /v1/me` and regenerated OpenAPI types.
- [x] A4 — Signed, expiring HttpOnly admin session and protected admin/provider APIs.
- [x] A5 — Nginx authorization boundary for admin data, metrics, and Grafana; public Compose overlay added.
- [x] A6 — Console admin gate, logout, session polling, and protected-query gating.
- [x] A7 — Playground verification states, authoritative team synchronization, clearing, and `401` invalidation.
- [x] A8 — Bounded authentication metrics, structured safe-result logging, Overview summary, and Grafana panels.
- [x] A9 — Backend, frontend, configuration, build, and static Compose verification.
- [x] A9-runtime — Local and public Compose health, Nginx/Grafana proxy enforcement, smoke, generated-artifact scan, and Playwright verification.
- [x] A10 — Authentication runbook, architecture, API, interview notes, public profile, and limitations documented.

Both profiles were exercised through Nginx; the normal local stack was restored afterward.
