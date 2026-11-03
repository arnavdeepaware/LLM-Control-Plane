# Authentication runbook

The demo separates three credentials because they represent different trust boundaries:

| Credential | Purpose | Browser storage | Public demo |
| --- | --- | --- | --- |
| Team API key | Authenticate data-plane chat requests and `/v1/me` | Memory or `sessionStorage` | Supplied manually to the reviewer |
| Admin access code | Open read-only console metadata and Grafana | Exchanged once for a signed HttpOnly cookie | Required |
| Development token | Mutate mock failures, spend, circuits, and rate-limit state | `sessionStorage` | Disabled |

## Local workflow

The normal Compose profile provides deterministic local-only defaults:

- admin access code: `local-admin-token`
- Team Alpha key: `alpha-secret-key`
- Team Beta key: `beta-secret-key`
- development token: `local-dev-token`

Run `docker compose up --build`, open `http://localhost:8080`, enter the admin code, then verify a team key in Playground. The admin code never remains in JavaScript after login. The signed admin cookie is HttpOnly, SameSite Strict, and valid for eight hours by default. “End admin session” clears it.

Team selection in Playground is configuration assistance only. `/v1/me` is authoritative: successful verification selects the actual team and its allowed model aliases. Changing or clearing the key immediately removes verified identity.

## Public-demo workflow

Provide non-default secrets and use the public overlay:

```bash
export TEAM_API_KEYS_JSON='{"team_alpha":"replace-with-a-long-random-value","team_beta":"replace-with-another-random-value"}'
export ADMIN_CONTROL_TOKEN='replace-with-a-long-admin-code'
export ADMIN_SESSION_SECRET='replace-with-at-least-32-random-characters'
docker compose -f docker-compose.yml -f docker-compose.public.yml up --build
```

The public profile exposes only the console port, requires secure cookies, removes direct gateway/Redis/Prometheus/Grafana ports, disables `/dev`, and builds without sample-key shortcuts. TLS must be terminated by the hosting platform; secure cookies will not work over plain HTTP.

Rotate team keys or the admin code by changing the environment values and redeploying. Rotating `ADMIN_SESSION_SECRET` invalidates every existing admin session. If a browser session expires, the console returns to the administrator access screen; sign in again with the current access code.

## API behavior

- Team endpoints accept `Authorization: Bearer <team-key>`.
- `/v1/me` returns sanitized team identity and does not touch rate limits, budgets, or providers.
- Missing, malformed, and invalid team credentials return `401` with `WWW-Authenticate: Bearer`.
- An authenticated team requesting a forbidden alias receives `403`.
- Admin login exchanges `Authorization: Bearer <admin-code>` at `POST /admin/session` for a signed cookie.
- `/admin/*`, `/providers/health`, and proxied `/grafana/*` require that cookie.

Raw credentials are never returned by discovery APIs or emitted as metric labels. Authentication metrics use only bounded result categories and a team ID on successful authentication.

## Security limitations

This is a public-demo control plane, not production IAM. It has one static environment-provided key per team and one shared admin access code. It does not implement a credential database, key hashes at rest, multiple application keys, expiration, overlapping rotation, revocation, OAuth/OIDC/SSO, RBAC, fine-grained scopes, individual operator identities, a persistent audit ledger, application-level brute-force protection, or automated TLS. Use a managed secret store, edge rate limiting/WAF, and platform TLS in a real deployment.
