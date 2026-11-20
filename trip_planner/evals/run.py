"""Run the behaviour scenarios against the live agent.

    python -m evals.run                      # all scenarios, once each
    python -m evals.run --repeats 3          # repeat each, to see run-to-run noise
    python -m evals.run --only injected      # scenarios whose name contains "injected"
    python -m evals.run --raw-injection      # bypass the snippet filter, so the
                                             # injection reaches the model itself

Needs GOOGLE_API_KEY, TAVILY_API_KEY and TICKETMASTER_API_KEY in .env. Prints a
pass rate per scenario and writes every trace to evals/results.jsonl.
"""
import argparse
import json
import os
import time
import uuid
from collections import defaultdict

from evals.scenarios import POISONED_HITS, SCENARIOS, Trace

HERE = os.path.dirname(os.path.abspath(__file__))


def trace_from(result_per_turn) -> Trace:
    """Build a Trace from the message lists the agent returned after each turn."""
    trace = Trace()
    seen = 0
    for turn, messages in enumerate(result_per_turn):
        new = messages[seen:]
        seen = len(messages)
        for m in new:
            kind = type(m).__name__
            if kind == "AIMessage":
                for call in getattr(m, "tool_calls", None) or []:
                    trace.tool_calls.append((turn, call["name"], call.get("args", {})))
            elif kind == "ToolMessage":
                trace.tool_outputs.append((turn, getattr(m, "name", ""), m.text))
        trace.replies.append(next((m.text for m in reversed(new) if type(m).__name__ == "AIMessage" and m.text), ""))
    return trace


def run_scenario(scenario, raw_injection=False) -> Trace:
    from agent import agent as agent_mod, tools

    patched = []
    if scenario.poisoned_search:
        class Poisoned:
            def __init__(self, **kwargs):
                pass

            def invoke(self, payload):
                return {"results": POISONED_HITS}
        patched.append((tools, "TavilySearch", tools.TavilySearch))
        tools.TavilySearch = Poisoned
        if raw_injection:
            patched.append((tools, "_looks_like_instruction", tools._looks_like_instruction))
            tools._looks_like_instruction = lambda text: False
    try:
        thread = f"eval-{uuid.uuid4()}"
        per_turn = []
        for text in scenario.turns:
            result = agent_mod.ask(text, thread)
            per_turn.append(list(result["messages"]))
        return trace_from(per_turn)
    finally:
        for obj, name, original in patched:
            setattr(obj, name, original)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--only", default="")
    p.add_argument("--raw-injection", action="store_true")
    p.add_argument("--pause", type=float, default=2.0)
    args = p.parse_args()

    passes = defaultdict(list)
    out_path = os.path.join(HERE, "results.jsonl")
    for repeat in range(args.repeats):
        for sc in SCENARIOS:
            if args.only and args.only.lower() not in sc.name.lower():
                continue
            try:
                trace = run_scenario(sc, raw_injection=args.raw_injection)
                outcomes = [check(trace) for check in sc.checks]
            except Exception as e:                       # a crash is a failure, not a skip
                trace, outcomes = Trace(), [(False, f"crashed: {e}")]
            ok = all(o for o, _ in outcomes)
            passes[sc.name].append(ok)
            failed = [msg for o, msg in outcomes if not o]
            print(f"[{repeat}] {'PASS' if ok else 'FAIL'}  {sc.name}" + (f"  <- {failed}" if failed else ""), flush=True)
            with open(out_path, "a") as f:
                f.write(json.dumps({"repeat": repeat, "scenario": sc.name, "passed": ok,
                                    "failed_checks": failed, "tools": [n for _, n, _ in trace.tool_calls],
                                    "final": trace.final}) + "\n")
            time.sleep(args.pause)

    print("\nPass rate per scenario")
    for name, results in passes.items():
        print(f"  {sum(results)}/{len(results)}  {name}")
    total = [r for v in passes.values() for r in v]
    print(f"\nOverall: {sum(total)}/{len(total)}")


if __name__ == "__main__":
    main()
