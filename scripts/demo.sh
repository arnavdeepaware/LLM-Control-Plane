#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
CHAT_PATH="/v1/chat/completions"

print_step() {
  printf "\n== %s ==\n" "$1"
}

request() {
  local label="$1"
  local expected="$2"
  shift 2

  print_step "$label"
  local body
  body="$(mktemp)"
  local status
  status="$(curl -sS -o "$body" -w "%{http_code}" "$@")"
  printf "HTTP %s (expected %s)\n" "$status" "$expected"
  python -m json.tool "$body" 2>/dev/null || sed -n '1,40p' "$body"
  rm -f "$body"

  if [ "$status" != "$expected" ]; then
    printf "Expected HTTP %s but got %s\n" "$expected" "$status" >&2
    return 1
  fi
}

chat_body='{"model":"smart-chat","messages":[{"role":"user","content":"Hello gateway"}]}'
cheap_body='{"model":"cheap-chat","messages":[{"role":"user","content":"Demo rate limit request"}]}'

request "Health" "200" \
  "$BASE_URL/health"

request "Successful chat request" "200" \
  -X POST "$BASE_URL$CHAT_PATH" \
  -H "Authorization: Bearer alpha-secret-key" \
  -H "Content-Type: application/json" \
  -d "$chat_body"

request "Missing auth is rejected" "401" \
  -X POST "$BASE_URL$CHAT_PATH" \
  -H "Content-Type: application/json" \
  -d "$chat_body"

request "Invalid API key is rejected" "401" \
  -X POST "$BASE_URL$CHAT_PATH" \
  -H "Authorization: Bearer wrong-key" \
  -H "Content-Type: application/json" \
  -d "$chat_body"

request "Disallowed model is rejected" "403" \
  -X POST "$BASE_URL$CHAT_PATH" \
  -H "Authorization: Bearer beta-secret-key" \
  -H "Content-Type: application/json" \
  -d "$chat_body"

request "Team limits" "200" \
  "$BASE_URL/admin/teams/team_alpha/limits"

request "Team usage" "200" \
  "$BASE_URL/admin/teams/team_alpha/usage"

request "Provider health" "200" \
  "$BASE_URL/providers/health"

print_step "Metrics contains gateway counters"
metrics_status="$(curl -sS -o /tmp/llm_gateway_demo_metrics.txt -w "%{http_code}" "$BASE_URL/metrics")"
printf "HTTP %s (expected 200)\n" "$metrics_status"
grep -E "llm_gateway_requests_total|llm_gateway_tokens_total|llm_gateway_cost_usd_total" /tmp/llm_gateway_demo_metrics.txt | sed -n '1,12p'
rm -f /tmp/llm_gateway_demo_metrics.txt
if [ "$metrics_status" != "200" ]; then
  printf "Expected metrics endpoint to return HTTP 200\n" >&2
  exit 1
fi

print_step "Rate limit demonstration with team_beta"
rate_limited=0
for _ in $(seq 1 25); do
  status="$(curl -sS -o /dev/null -w "%{http_code}" \
    -X POST "$BASE_URL$CHAT_PATH" \
    -H "Authorization: Bearer beta-secret-key" \
    -H "Content-Type: application/json" \
    -d "$cheap_body")"
  printf "%s " "$status"
  if [ "$status" = "429" ]; then
    rate_limited=1
  fi
done
printf "\n"

if [ "$rate_limited" != "1" ]; then
  printf "Expected at least one 429 response during rate-limit demo\n" >&2
  exit 1
fi

printf "\nDemo complete.\n"
