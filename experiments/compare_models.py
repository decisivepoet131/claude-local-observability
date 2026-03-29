#!/usr/bin/env python3
"""
Prompt experiment runner — runs the same prompt across one or more models
and logs every input, output, token count, and cost to Langfuse.

Usage:
  python compare_models.py "explain recursion in one sentence"
  python compare_models.py "explain recursion" --models claude-sonnet-4-6 claude-haiku-4-5-20251001
  python compare_models.py "explain recursion" --experiment "clarity-test-v1"
  python compare_models.py "explain recursion" --system "You are a concise technical writer"
  python compare_models.py "explain recursion" --runs 3   # same model, 3 times (variance test)

Results appear in Langfuse at http://localhost:3001
Group by experiment name to compare across runs.
"""

import argparse
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()

LANGFUSE_HOST       = os.getenv("LANGFUSE_HOST", "http://localhost:3001")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")

DEFAULT_MODELS    = ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"]
DEFAULT_MAX_TOKENS = 1024

# Approximate cost per 1M tokens (USD) — update as pricing changes
MODEL_COSTS = {
    "claude-opus-4-6":             {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6":           {"input":  3.00, "output": 15.00},
    "claude-haiku-4-5-20251001":   {"input":  0.80, "output":  4.00},
}

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = MODEL_COSTS.get(model, {"input": 0, "output": 0})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


def run_single(
    client: Anthropic,
    langfuse: Langfuse,
    trace,
    prompt: str,
    model: str,
    system_prompt: str | None,
    run_index: int,
) -> dict:
    messages = [{"role": "user", "content": prompt}]
    kwargs = {"model": model, "max_tokens": DEFAULT_MAX_TOKENS, "messages": messages}
    if system_prompt:
        kwargs["system"] = system_prompt

    span_name = f"{model}" if run_index == 0 else f"{model} (run {run_index + 1})"
    generation = trace.generation(name=span_name, model=model, input=messages)

    response = client.messages.create(**kwargs)
    output = response.content[0].text
    cost = estimate_cost(model, response.usage.input_tokens, response.usage.output_tokens)

    generation.end(
        output=output,
        usage={
            "input":  response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
        metadata={"estimated_cost_usd": cost},
    )

    return {
        "model":         model,
        "output":        output,
        "input_tokens":  response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd":      cost,
    }


def run_experiment(
    prompt:          str,
    models:          list[str],
    experiment_name: str | None,
    system_prompt:   str | None,
    runs:            int,
) -> None:
    langfuse = Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
    )
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    trace = langfuse.trace(
        name=experiment_name or "prompt-experiment",
        input=prompt,
        metadata={"system_prompt": system_prompt, "models": models, "runs": runs},
        tags=["experiment"],
    )

    all_results = []
    for model in models:
        for i in range(runs):
            label = f"{model}" + (f" run {i+1}/{runs}" if runs > 1 else "")
            print(f"\n{'─'*60}")
            print(f"  {label}")
            print(f"{'─'*60}")

            result = run_single(client, langfuse, trace, prompt, model, system_prompt, i)
            all_results.append(result)

            print(result["output"])
            print(f"\n  tokens  in={result['input_tokens']}  out={result['output_tokens']}"
                  f"  cost=~${result['cost_usd']:.5f}")

    # Summary
    print(f"\n{'═'*60}")
    print("  SUMMARY")
    print(f"{'═'*60}")
    for r in all_results:
        print(f"  {r['model']:<40}  ${r['cost_usd']:.5f}  "
              f"{r['input_tokens']}in / {r['output_tokens']}out")

    total_cost = sum(r["cost_usd"] for r in all_results)
    print(f"\n  Total estimated cost: ${total_cost:.5f}")
    print(f"\n  View in Langfuse → {LANGFUSE_HOST}")

    langfuse.flush()


def main():
    parser = argparse.ArgumentParser(
        description="Run prompt experiments and log to Langfuse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("prompt",                              help="Prompt to test")
    parser.add_argument("--models",     nargs="+",            default=DEFAULT_MODELS,
                        help="Models to compare (space-separated)")
    parser.add_argument("--experiment", default=None,         help="Experiment name for grouping in Langfuse")
    parser.add_argument("--system",     default=None,         help="System prompt")
    parser.add_argument("--runs",       type=int, default=1,  help="Number of times to run each model (variance testing)")
    args = parser.parse_args()

    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        print("Error: Langfuse API keys not set.")
        print("1. Open http://localhost:3001 and create an account")
        print("2. Create a project → Settings → API Keys")
        print("3. Copy experiments/.env.example to experiments/.env and fill in the keys")
        sys.exit(1)

    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not set in experiments/.env")
        sys.exit(1)

    run_experiment(args.prompt, args.models, args.experiment, args.system, args.runs)


if __name__ == "__main__":
    main()
