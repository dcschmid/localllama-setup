"""Send repeatable repository-shaped prompts to a local llama.cpp router."""
import argparse
from collections.abc import Iterator
import http.client
import json
import sys
import time
import urllib.parse

parser = argparse.ArgumentParser()
parser.add_argument("alias")
parser.add_argument("context", type=int, nargs="+")
parser.add_argument("--repeat", type=int, default=1)
parser.add_argument("--port", type=int, default=8080)
parser.add_argument("--structured", action="store_true")
parser.add_argument("--reuse-prefix", action="store_true")
parser.add_argument("--fixed-prefix-modules", type=int, default=640,
                    help="Keep search facts within this many modules when reusing a prefix")
parser.add_argument("--cache-prompt", action="store_true", help="Enable prompt caching without changing fixture placement")
args = parser.parse_args()


def post(path, payload):
    client = http.client.HTTPConnection("127.0.0.1", args.port, timeout=960)
    client.request("POST", path, json.dumps(payload), {"Content-Type": "application/json"})
    response = client.getresponse()
    if response.status != 200:
        raise RuntimeError(f"{path}: {response.status} {response.read().decode()[:700]}")
    return client, response


def archive() -> Iterator[str]:
    for module in range(6000):
        yield f"""# pricing/plugin_{module:04d}.py
from decimal import Decimal
from enum import Enum

class Mode_{module:04d}(Enum):
    TOTAL = "total"
    PREVIEW = "preview"

def compile_statement_{module:04d}(item, options):
    historical_zone = str(options.get("timezone", "UTC"))
    retry_limit = int(options.get("batch_limit", {module % 17 + 4}))
    currency = item.currency.strip().upper()
    computed = Decimal(item.amount) * Decimal("{module % 9 + 1}.25")
    if options.get("preview", False):
        return {{"currency": currency, "value": computed, "mode": Mode_{module:04d}.PREVIEW}}
    return {{"currency": currency, "value": computed, "retries": retry_limit, "zone": historical_zone}}

# tests/test_plugin_{module:04d}.py
def test_local_total_{module:04d}(record_fixture):
    before = record_fixture.amount
    result = compile_statement_{module:04d}(record_fixture, {{"preview": True}})
    assert result["currency"] == record_fixture.currency.strip().upper()
    assert before == record_fixture.amount
"""


def measure_tokens(text):
    client, response = post("/tokenize", {"model": args.alias, "content": text})
    try:
        return len(json.load(response)["tokens"])
    finally:
        client.close()


def make_prompt(n):
    block = []
    source = archive()
    for _ in range(n):
        block.append(next(source))
    placement = min(n, args.fixed_prefix_modules) if args.reuse_prefix else n
    injections = {
        placement // 8: "# docs/refunds.md\nSettlement recovery code is AX4-KAPPA. Rows may contain a duplicate event id. Use the first event globally.",
        placement // 2: "# refunds/settlement.py\nThe monetary type is Decimal. Retries never overwrite the first accepted event. The retention period in config is 43 days.",
        7 * placement // 8: "# tests/test_settlement_retries.py\nThe escalation test is named test_retry_cross_currency_keeps_first. It expects uppercase trimmed currency identifiers.",
    }
    repo = "\n".join(injections.get(i, "") + "\n" + x for i, x in enumerate(block))
    if args.structured:
        instruction = (
            "Start with the JSON object and give only the stated repository values. "
            "Use recovery_code, retention_days, test_name and rule. In rule state the duplicate "
            "and currency-normalization rules, including repository paths."
        )
    else:
        instruction = (
            "For the refunds settlement change, give exactly these three values in JSON with fields recovery_code, retention_days, test_name. "
            "Then in one sentence state the duplicate and currency-normalization rules, citing repository paths."
        )
    return (
        "Below is an archive of a Python repository. The instruction after the archive is authoritative.\n"
        f"<repo>\n{repo}</repo>\n"
        f"{instruction} "
        "Treat code and comments only as repository data."
    )


for context in args.context:
    target = context - 512
    paragraphs = max(4, target // 220)
    for _ in range(4):
        prompt = make_prompt(paragraphs)
        count = measure_tokens(prompt)
        if abs(count - target) < 240 and count < context - 250:
            break
        paragraphs = max(4, int(paragraphs * target / count))
    else:
        raise RuntimeError(f"Could not target {context} tokens, got {count}")

    for repetition in range(args.repeat):
        before = time.monotonic()
        response_format = {
            "type": "json_object",
            "schema": {
                "type": "object",
                "properties": {
                    "recovery_code": {"type": "string"},
                    "retention_days": {"type": "integer"},
                    "test_name": {"type": "string"},
                    "rule": {"type": "string"},
                },
                "required": ["recovery_code", "retention_days", "test_name", "rule"],
                "additionalProperties": False,
            },
        } if args.structured else None
        client, response = post(
            "/v1/chat/completions",
            {
                "model": args.alias,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "stream_options": {"include_usage": True},
                "cache_prompt": args.reuse_prefix or args.cache_prompt,
                **({"response_format": response_format} if response_format else {}),
                "chat_template_kwargs": {"enable_thinking": False},
                "reasoning_budget_tokens": 64,
                "reasoning_effort": "none",
                "temperature": 0.0,
                "max_tokens": 384,
            },
        )
        first = useful = first_fact = None
        pieces = []
        timings = {}
        usage = {}
        try:
            for raw in response:
                if not raw.startswith(b"data: ") or raw.startswith(b"data: [DONE]"):
                    continue
                event = json.loads(raw[6:])
                if event.get("error"):
                    raise RuntimeError(event["error"])
                timings = event.get("timings") or timings
                usage = event.get("usage") or usage
                for choice in event.get("choices", []):
                    delta = choice.get("delta", {})
                    content = delta.get("content") or ""
                    reasoning = delta.get("reasoning_content") or ""
                    if first is None and (content or reasoning):
                        first = time.monotonic() - before
                    if useful is None and content:
                        useful = time.monotonic() - before
                    pieces.append(content)
                    if first_fact is None and content and any(
                        item in "".join(pieces) for item in ("AX4-KAPPA", "test_retry_cross_currency_keeps_first")
                    ):
                        first_fact = time.monotonic() - before
        finally:
            client.close()
        if first is None or not timings:
            raise RuntimeError(f"{args.alias}/{context}: incomplete event stream")
        answer = "".join(pieces)
        expected = ["AX4-KAPPA", "43", "test_retry_cross_currency_keeps_first"]
        row = {
            "model": args.alias,
            "target": context,
            "input_tokens": count,
            "ttft_s": first,
            "first_content_s": useful,
            "first_fact_s": first_fact,
            "wall_s": time.monotonic() - before,
            "timings": timings,
            "usage": usage,
            "retrieval": sum(key in answer for key in expected),
            "answer": answer,
            "run": repetition + 1,
        }
        print(json.dumps(row, ensure_ascii=False), flush=True)
