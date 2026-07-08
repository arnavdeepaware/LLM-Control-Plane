import argparse
import asyncio
import statistics
import sys
import time
from dataclasses import dataclass

import httpx


@dataclass
class RequestResult:
    status_code: int | None
    latency_ms: float
    error: str = ""


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * 0.95)
    return sorted_values[index]


async def _send_chat_request(
    client: httpx.AsyncClient,
    url: str,
    api_key: str,
    model: str,
    request_index: int,
) -> RequestResult:
    started = time.perf_counter()
    try:
        response = await client.post(
            url,
            json={
                "model": model,
                "messages": [{"role": "user", "content": f"Load test request {request_index}"}],
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        latency_ms = (time.perf_counter() - started) * 1000
        if 200 <= response.status_code < 300:
            body = response.json()
            if body.get("provider") != "mock" or "usage" not in body:
                return RequestResult(response.status_code, latency_ms, "invalid success response shape")
        return RequestResult(response.status_code, latency_ms)
    except (httpx.HTTPError, ValueError) as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return RequestResult(None, latency_ms, str(exc))


async def run_load_test(
    base_url: str,
    total_requests: int,
    concurrency: int,
    model: str,
    api_key: str,
    timeout_seconds: float,
) -> tuple[list[RequestResult], float]:
    semaphore = asyncio.Semaphore(concurrency)
    url = _url(base_url, "/v1/chat/completions")
    started = time.perf_counter()

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        async def run_one(index: int) -> RequestResult:
            async with semaphore:
                return await _send_chat_request(client, url, api_key, model, index)

        results = await asyncio.gather(*(run_one(index) for index in range(total_requests)))

    elapsed_seconds = time.perf_counter() - started
    return list(results), elapsed_seconds


def _print_summary(results: list[RequestResult], elapsed_seconds: float, fail_on_rate_limit: bool) -> int:
    latencies = [result.latency_ms for result in results]
    successes = [result for result in results if result.status_code is not None and 200 <= result.status_code < 300]
    rate_limited = [result for result in results if result.status_code == 429]
    transport_errors = [result for result in results if result.status_code is None]
    server_errors = [result for result in results if result.status_code is not None and result.status_code >= 500]
    unexpected_client_errors = [
        result
        for result in results
        if result.status_code is not None and 400 <= result.status_code < 500 and result.status_code != 429
    ]
    invalid_shape_errors = [result for result in results if result.error and result.status_code is not None]
    errors = transport_errors + server_errors + unexpected_client_errors + invalid_shape_errors

    average_latency = statistics.mean(latencies) if latencies else 0.0
    requests_per_second = len(results) / elapsed_seconds if elapsed_seconds > 0 else 0.0

    print("Load test complete")
    print(f"Total requests: {len(results)}")
    print(f"Successes: {len(successes)}")
    print(f"Rate limited: {len(rate_limited)}")
    print(f"Errors: {len(errors)}")
    print(f"Average latency ms: {average_latency:.2f}")
    print(f"P95 latency ms: {_p95(latencies):.2f}")
    print(f"Requests/sec: {requests_per_second:.2f}")

    failed = bool(errors) or not successes or (fail_on_rate_limit and bool(rate_limited))
    print(f"Result: {'FAIL' if failed else 'PASS'}")

    if errors:
        first_error = errors[0]
        print(f"First error: status={first_error.status_code} detail={first_error.error}")

    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a modest local load test against LLM Gateway.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--model", default="cheap-chat")
    parser.add_argument("--api-key", default="alpha-secret-key")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--fail-on-rate-limit", action="store_true")
    args = parser.parse_args()

    if args.requests <= 0:
        print("FAIL requests must be greater than 0")
        return 1
    if args.concurrency <= 0:
        print("FAIL concurrency must be greater than 0")
        return 1

    results, elapsed_seconds = asyncio.run(
        run_load_test(
            base_url=args.base_url,
            total_requests=args.requests,
            concurrency=args.concurrency,
            model=args.model,
            api_key=args.api_key,
            timeout_seconds=args.timeout_seconds,
        )
    )
    return _print_summary(results, elapsed_seconds, args.fail_on_rate_limit)


if __name__ == "__main__":
    sys.exit(main())
