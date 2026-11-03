# V1 developer console

Start Docker, then run `docker compose up --build`. The console is at `http://localhost:8080`; the gateway is at `:8000`, Prometheus at `:9090`, and Grafana at `:3000/grafana/`. Enter the local admin access code `local-admin-token` before the console loads protected data. The local Test Lab token defaults to `local-dev-token`; set the environment values in `.env` to change either. See [authentication.md](authentication.md) for team keys, public deployment, rotation, and session behavior.

## Capability matrix

| Feature | Current state | UI behavior |
| --- | --- | --- |
| Mock chat | Available | Playground sends real gateway requests and labels responses simulated |
| Team authentication | Available | `/v1/me` verifies the key and the UI displays the resolved identity before chat |
| Admin authentication | Available | Signed HttpOnly session protects console metadata and proxied Grafana |
| Team usage and provider circuits | Available | Overview, Teams, and Providers poll live endpoints |
| Failure injection and reset | Local development only | Test Lab appears when enabled and requires a separate token |
| Prometheus and Grafana | Available | Embedded dashboard and full Grafana link |
| Real providers | Pending adapter | Capability flag controls future provider display |
| Streaming | Pending API implementation | Playground labels it unavailable |
| Usage history | Pending persistent store | Current counters only; no history view |
| Routing edits | Pending authenticated control plane | Read-only configuration; no edit form |

The Test Lab presets reset relevant state, send gateway requests, and log expected versus actual results. Use the Playground for your own follow-up requests and response inspection. Resetting circuits or queued failures for a team also affects any provider targets shared with other teams.

## Public demo profile

Use `docker-compose.public.yml` with explicit `TEAM_API_KEYS_JSON`, `ADMIN_CONTROL_TOKEN`, and `ADMIN_SESSION_SECRET`. The overlay disables development controls and sample-key shortcuts, enables secure cookies, and exposes only the console port. The local Compose defaults are deliberately for workstation use.

## Architecture

```text
Browser → Nginx console :8080 → FastAPI gateway :8000 → Redis
                    └──────→ Grafana :3000 → Prometheus :9090 → gateway /metrics
```

The console polls readiness every five seconds and runtime data every ten seconds while the tab is visible. The UI shows partial failure states and refresh timestamps. `/health` is liveness; `/ready` checks Redis and configuration. `/providers/health` reports local circuit state, not an active provider probe.

## Scenario guide

1. Enter the admin access code, then open Test Lab and enter the development token.
2. Reset all demo state.
3. Queue a transient retry or primary fallback, then submit `smart-chat` from Team Alpha in Playground.
4. Inspect `model_served`, `fallback_used`, request ID, tokens, latency, and estimated cost.
5. Seed Team Alpha's daily budget to its limit, then submit another request and expect `402`.
6. Reset state, exhaust the Team Beta request bucket, and expect `429` with retry timing.
7. Open Observability after requests and inspect metrics in Grafana.

## Next phase dependencies

Real provider adapters need capability reporting and accurate token/cost data. Streaming requires a new response contract and retry/accounting rules. Usage history requires durable events. Routing edits require authenticated administration and configuration rollout. The console deliberately exposes none of these as working controls yet.
