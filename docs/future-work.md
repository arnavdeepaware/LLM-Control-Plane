# Future Work

The next improvements should keep the same control-plane architecture while increasing real-world depth.

## Provider Adapters

- Add environment-gated OpenAI, Anthropic, or Ollama adapters.
- Keep external API calls out of automated tests.
- Add mocked transport tests for each adapter.
- Preserve normalized `ChatCompletionResponse` output.

## Cost And Usage

- Add provider/model-specific tokenizer support.
- Store usage events in a persistent database.
- Add monthly reports by team, model alias, and provider target.
- Track budget reservations before provider calls for stronger overspend prevention.

## Configuration

- Add config validation tooling that can run before startup.
- Add a safe config reload strategy.
- Support secret references instead of raw local keys in YAML.

## Reliability

- Add provider-level timeout configuration.
- Add per-route retry policies.
- Add fallback policies based on error class or cost.
- Add circuit-breaker admin reset controls with authentication.

## Observability

- Add OpenTelemetry traces.
- Add structured audit events for auth failures and budget blocks.
- Add alert rules for provider error rates, circuit-open state, and budget exhaustion.

## Delivery

- Add GitHub Actions for `pytest` and Docker Compose config validation.
- Add release documentation.
- Add example screenshots to `docs/images/`.

## Product Scope

- Streaming support.
- Admin authentication and scoped admin tokens.
- Team onboarding workflow.
- Web dashboard if this evolves beyond backend portfolio scope.
