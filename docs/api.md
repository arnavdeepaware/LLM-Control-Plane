# API Reference

The gateway exposes a small HTTP API for health checks, chat completions, team usage, provider health, and Prometheus metrics.

## Base URL

Local default:

```text
http://localhost:8000
```

## Authentication

Chat requests use a Bearer API key:

```http
Authorization: Bearer alpha-secret-key
```

The local Compose profile injects these deterministic demo credentials through `TEAM_API_KEYS_JSON`:

| Team | API key | Allowed models |
| --- | --- | --- |
| `team_alpha` | `alpha-secret-key` | `smart-chat`, `cheap-chat` |
| `team_beta` | `beta-secret-key` | `cheap-chat` |

These values are not stored in team YAML and must be replaced for the public profile. Administrative endpoints use the separate signed session described below.

## Error Envelope

Most API errors use:

```json
{
  "error": "error_slug",
  "message": "Human readable message"
}
```

Rate-limit responses also include `Retry-After`.

## `GET /`

Returns basic service metadata.

```bash
curl -s http://localhost:8000/
```

Expected response:

```json
{
  "name": "LLM Gateway",
  "version": "0.1.0"
}
```

## `GET /health`

Health endpoint for local checks and Docker smoke tests.

```bash
curl -s http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

## `GET /v1/me`

Verifies a team Bearer key without consuming rate limits, checking budgets, or calling a provider. It returns the resolved team name, allowed aliases, limits, and budgets; credential and routing details are omitted.

```bash
curl -s http://localhost:8000/v1/me \
  -H "Authorization: Bearer alpha-secret-key"
```

Missing, malformed, and invalid credentials return `401` with `WWW-Authenticate: Bearer`.

## `POST /v1/chat/completions`

Main gateway endpoint.

```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer alpha-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "smart-chat",
    "messages": [
      {"role": "user", "content": "Hello gateway"}
    ]
  }'
```

Request fields:

| Field | Type | Notes |
| --- | --- | --- |
| `model` | string | Team-facing model alias such as `smart-chat` |
| `messages` | array | Chat messages with `system`, `user`, or `assistant` role |
| `stream` | boolean | Accepted by schema, streaming is not implemented |
| `priority` | string | Accepted by schema for future use |

Expected response shape:

```json
{
  "id": "chatcmpl_mock_<dynamic>",
  "object": "chat.completion",
  "model_requested": "smart-chat",
  "model_served": "mock:mock-smart-chat",
  "provider": "mock",
  "fallback_used": false,
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Mock response from mock-smart-chat for alias 'smart-chat'. Received 1 message(s)."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "input_tokens": 2,
    "output_tokens": 20,
    "total_tokens": 22
  }
}
```

## Auth Failure

```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"smart-chat","messages":[{"role":"user","content":"Hello"}]}'
```

Expected status: `401`

```json
{
  "error": "unauthorized",
  "message": "Missing authorization header"
}
```

## Model Access Failure

`team_beta` cannot use `smart-chat`.

```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer beta-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"smart-chat","messages":[{"role":"user","content":"Hello"}]}'
```

Expected status: `403`

```json
{
  "error": "forbidden",
  "message": "Model 'smart-chat' is not allowed for team 'Team Beta'"
}
```

## Rate Limit Failure

`team_beta` has a lower request-per-minute limit. Repeated requests return:

Expected status: `429`

```json
{
  "error": "rate_limit_exceeded",
  "message": "Team team_beta exceeded 20 requests per minute.",
  "retry_after_seconds": 3
}
```

## Budget Failure

When a team has already reached its configured budget:

Expected status: `402`

```json
{
  "error": "budget_exceeded",
  "message": "Team team_alpha reached its daily budget of $5.00."
}
```

## Admin session

Exchange the separate admin access code for an expiring HttpOnly cookie. The code is not a team key.

```bash
curl -s -c /tmp/llm-admin-cookie -X POST http://localhost:8000/admin/session \
  -H "Authorization: Bearer local-admin-token"
```

Pass `-b /tmp/llm-admin-cookie` when calling `/admin/*` or `/providers/health`. `GET /admin/session` reports session status, and `DELETE /admin/session` logs out. Proxied Grafana uses the same browser cookie.

## `GET /admin/teams/{team_id}/usage`

Returns current rate-limit visibility, spend, and configured budgets.

```bash
curl -s -b /tmp/llm-admin-cookie http://localhost:8000/admin/teams/team_alpha/usage
```

Expected response shape:

```json
{
  "team_id": "team_alpha",
  "rate_limits": {
    "requests_per_minute": 60,
    "tokens_per_minute": 50000
  },
  "tokens_this_minute": 22,
  "spend": {
    "daily_usd": 0.00005,
    "monthly_usd": 0.00005
  },
  "budgets": {
    "daily_usd": 5.0,
    "monthly_usd": 50.0
  }
}
```

## `GET /admin/teams/{team_id}/limits`

Returns configured limits for a team.

```bash
curl -s http://localhost:8000/admin/teams/team_alpha/limits
```

Expected response:

```json
{
  "team_id": "team_alpha",
  "rate_limits": {
    "requests_per_minute": 60,
    "tokens_per_minute": 50000
  },
  "budgets": {
    "daily_usd": 5.0,
    "monthly_usd": 50.0
  }
}
```

## `GET /providers/health`

Returns configured provider targets and circuit-breaker state.

```bash
curl -s http://localhost:8000/providers/health
```

Expected response shape:

```json
{
  "providers": [
    {
      "provider": "mock",
      "model": "mock-smart-chat",
      "circuit_state": "closed",
      "recent_failures": 0,
      "last_failure_at": null
    }
  ]
}
```

## `GET /metrics`

Prometheus scrape endpoint.

```bash
curl -s http://localhost:8000/metrics
```

Expected content type: Prometheus text format.

Expected metric names include:

```text
llm_gateway_requests_total
llm_gateway_request_latency_seconds
llm_gateway_provider_errors_total
llm_gateway_fallbacks_total
llm_gateway_retries_total
llm_gateway_rate_limited_total
llm_gateway_budget_blocked_total
llm_gateway_tokens_total
llm_gateway_cost_usd_total
llm_gateway_circuit_state
```
