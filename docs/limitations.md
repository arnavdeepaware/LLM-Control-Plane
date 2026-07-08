# Limitations

This project is a production-style portfolio implementation, not a fully managed production service. The limitations below are intentional and documented so reviewers can understand the current boundary clearly.

## Provider Scope

- Only `MockProvider` is implemented.
- No real OpenAI, Anthropic, or Ollama provider calls are made.
- Tests do not require real provider credentials.
- Streaming responses are not implemented.

## Configuration

- Config is loaded from YAML at process startup.
- There is no dynamic config reload endpoint.
- API keys in the sample config are local demo secrets and should not be used in production.
- There is no encrypted secret store integration.

## Persistence

- Redis stores rate-limit buckets, token visibility, and budget spend.
- There is no relational database or long-term request history.
- Budget tracking is sufficient for a local demo, but not an accounting-grade ledger.

## Cost Estimation

- Token counting is deterministic and simple for `MockProvider`.
- Real provider tokenization can differ by model and provider.
- Prices are static YAML values.

## Operations

- Docker Compose is intended for local review and demos.
- Kubernetes is intentionally out of scope.
- There is no CI workflow in the repository yet.
- There is no alerting integration.

## Security

- The gateway avoids logging raw API keys and prompt content.
- Sample API keys are checked in for local demonstration only.
- There is no key rotation system.
- There is no per-route admin authentication for the demo admin endpoints.

## Observability

- Prometheus metrics cover the core gateway behavior.
- Full distributed tracing is not implemented.
- Logs are structured JSON but are not shipped to an external log platform.
