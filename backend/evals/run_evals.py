"""On-demand evals. Usage (from backend/):

    python -m evals.run_evals guardrails                # input + output sets, LLM if ambiguous
    python -m evals.run_evals guardrails --no-llm       # rules only; ambiguous reported separately
    python -m evals.run_evals guardrails --set heldout  # held-out prompts (not used to tune rules)

Quota-aware: LLM classifier answers are cached on disk (data/cache/guard_llm.json) and calls
are throttled, so re-runs cost nothing and a partial run can simply be re-run.
"""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from app.guardrails.input_guard import check_input
from app.guardrails.output_guard import check_output
from app.observability.logging import setup_logging

EVALS = Path(__file__).resolve().parent
THROTTLE_SECONDS = 4.0


def _load(name: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (EVALS / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def run_input(rows: list[dict], use_llm: bool) -> dict:
    results, llm_calls = [], 0
    for row in rows:
        from app.guardrails import input_guard

        cached_before = input_guard._cache_get(
            __import__("hashlib").sha256(row["prompt"].strip().lower().encode()).hexdigest()
        )
        res = check_input(row["prompt"], use_llm=use_llm)
        if res.decided_by == "llm" and cached_before is None:
            llm_calls += 1
            time.sleep(THROTTLE_SECONDS)
        got = "refuse" if res.action == "refuse" else "allow"
        results.append(
            {
                **row,
                "got": got,
                "ok": got == row["expected"],
                "decided_by": res.decided_by,
                "category": res.category,
                "reason": res.reason,
            }
        )
    return {"rows": results, "llm_calls": llm_calls}


def run_output(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        res = check_output(row["text"])
        got = "flag" if res.modified else "pass"
        out.append(
            {
                **row,
                "got": got,
                "ok": got == row["expected"],
                "violations": [v.category for v in res.violations],
            }
        )
    return out


def _rate(rows: list[dict], label: str | None = None) -> str:
    sel = [r for r in rows if label is None or r["label"] == label]
    ok = sum(r["ok"] for r in sel)
    return f"{ok}/{len(sel)} ({100 * ok / len(sel):.1f}%)" if sel else "n/a"


def cmd_guardrails(args: argparse.Namespace) -> None:
    file = "guardrail_heldout.jsonl" if args.set == "heldout" else "guardrail_set.jsonl"
    data = run_input(_load(file), use_llm=not args.no_llm)
    rows = data["rows"]
    by_rules = [r for r in rows if r["decided_by"] == "rules"]
    by_llm = [r for r in rows if r["decided_by"] == "llm"]
    unresolved = [r for r in rows if r["reason"] == "ambiguous-unresolved"]

    print(f"\n=== INPUT GUARD: {file} ===")
    print(f"steering prompts refused : {_rate(rows, 'steering')}   (target 100%)")
    print(f"normal prompts allowed   : {_rate(rows, 'normal')}")
    if any(r["label"] == "ambiguous" for r in rows):
        print(f"ambiguous prompts correct: {_rate(rows, 'ambiguous')}")
    print(f"overall                  : {_rate(rows)}")
    print(
        f"decided by               : {len(by_rules)} rules, {len(by_llm)} llm, "
        f"{len(unresolved)} unresolved (new llm calls: {data['llm_calls']})"
    )
    for r in rows:
        if not r["ok"]:
            print(
                f"  FAIL [{r['id']}] expected {r['expected']}, got {r['got']} "
                f"({r['decided_by']}): {r['prompt']}"
            )

    report = {"input_file": file, "input": rows}
    if args.set != "heldout":
        out_rows = run_output(_load("guardrail_output_set.jsonl"))
        ok = sum(r["ok"] for r in out_rows)
        print("\n=== OUTPUT GUARD: guardrail_output_set.jsonl ===")
        pct = 100 * ok / len(out_rows)
        print(f"correct (flag bad / pass clean): {ok}/{len(out_rows)} ({pct:.1f}%)")
        for r in out_rows:
            if not r["ok"]:
                print(f"  FAIL [{r['id']}] expected {r['expected']}, got {r['got']}: {r['text']}")
        report["output"] = out_rows

    out_dir = EVALS / "results"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"guardrails_{args.set}_{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"\nreport written to {path.relative_to(EVALS.parent)}")


def main() -> None:
    setup_logging(level=40)
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("guardrails")
    g.add_argument("--no-llm", action="store_true")
    g.add_argument("--set", choices=["main", "heldout"], default="main")
    g.set_defaults(fn=cmd_guardrails)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
