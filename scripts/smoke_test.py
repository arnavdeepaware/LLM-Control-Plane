import argparse
import sys
from dataclasses import dataclass

import httpx


CHAT_BODY = {
    "model": "smart-chat",
    "messages": [{"role": "user", "content": "Hello gateway"}],
}


@dataclass
class CheckResult:
    name: str
    expected_status: int
    passed: bool
    detail: str = ""


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _check_status(name: str, response: httpx.Response, expected_status: int) -> CheckResult:
    if response.status_code != expected_status:
        return CheckResult(
            name=name,
            expected_status=expected_status,
            passed=False,
            detail=f"expected {expected_status}, got {response.status_code}",
        )
    return CheckResult(name=name, expected_status=expected_status, passed=True)


def run_smoke_checks(base_url: str, timeout_seconds: float) -> list[CheckResult]:
    results: list[CheckResult] = []
    with httpx.Client(timeout=timeout_seconds) as client:
        health = client.get(_url(base_url, "/health"))
        result = _check_status("health", health, 200)
        if result.passed and health.json() != {"status": "ok"}:
            result = CheckResult("health", 200, False, "unexpected health body")
        results.append(result)

        metrics = client.get(_url(base_url, "/metrics"))
        result = _check_status("metrics", metrics, 200)
        if result.passed and "llm_gateway_requests_total" not in metrics.text:
            result = CheckResult("metrics", 200, False, "gateway metric name missing")
        results.append(result)

        chat = client.post(
            _url(base_url, "/v1/chat/completions"),
            json=CHAT_BODY,
            headers={"Authorization": "Bearer alpha-secret-key"},
        )
        result = _check_status("chat", chat, 200)
        if result.passed:
            body = chat.json()
            if body.get("provider") != "mock" or body.get("model_served") != "mock:mock-smart-chat":
                result = CheckResult("chat", 200, False, "unexpected chat response shape")
        results.append(result)

        missing_auth = client.post(_url(base_url, "/v1/chat/completions"), json=CHAT_BODY)
        results.append(_check_status("missing_auth", missing_auth, 401))

        invalid_auth = client.post(
            _url(base_url, "/v1/chat/completions"),
            json=CHAT_BODY,
            headers={"Authorization": "Bearer wrong-key"},
        )
        results.append(_check_status("invalid_auth", invalid_auth, 401))

        disallowed_model = client.post(
            _url(base_url, "/v1/chat/completions"),
            json=CHAT_BODY,
            headers={"Authorization": "Bearer beta-secret-key"},
        )
        results.append(_check_status("disallowed_model", disallowed_model, 403))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run smoke checks against a running LLM Gateway.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    args = parser.parse_args()

    try:
        results = run_smoke_checks(args.base_url, args.timeout_seconds)
    except (httpx.HTTPError, ValueError) as exc:
        print(f"FAIL smoke_setup {exc}")
        return 1

    passed = 0
    for result in results:
        if result.passed:
            passed += 1
            print(f"PASS {result.name} {result.expected_status}")
        else:
            print(f"FAIL {result.name} {result.detail}")

    if passed == len(results):
        print(f"Smoke test passed: {passed}/{len(results)} checks")
        return 0

    print(f"Smoke test failed: {passed}/{len(results)} checks")
    return 1


if __name__ == "__main__":
    sys.exit(main())
