"""Outcome-knowledge probe: behavioural verification of the model's training cutoff.

Registered leakage control 1. The production snapshot ``gpt-5-mini-2025-08-07``
has a documented training cutoff of May 31, 2024, which predates the 2025
Chilean campaign and both election rounds -- so it should not be able to hold
the outcome parametrically. This script tests that behaviourally rather than
taking the documentation on trust.

The battery, the repetition count and the scoring categories are fixed by the
17 August 2026 selection memo, section 4. Items 1-2 are in-cutoff anchors the
model *should* answer correctly; items 3-8 concern post-cutoff events it should
not be able to answer. Per the registration, a correct and specific answer on
item 5 or 7 halts the production run pending reassessment.

Run before any production interview, with web search disabled:

    python -m scripts.outcome_knowledge_probe
    python -m scripts.outcome_knowledge_probe --dry-run
    python -m scripts.outcome_knowledge_probe --repetitions 3 --out-dir <path>

Each run writes two files: ``probe_manifest.json`` (the conditions the probe ran
under, and the verdict) and ``probe_responses.csv`` (one row per call, carrying
the prompt, the response and its metadata). Together they are the auditable
record that ships with the registration materials.

Scoring is deliberately left to a human. This script classifies each response
as a refusal or a non-refusal, which is mechanically decidable; whether a
non-refusal is *correct* or *hallucinated* depends on the real-world outcome
and is recorded by an analyst in the ``score`` column of the emitted CSV.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.base_config import GPT_MODEL  # noqa: E402
from src.utils import openai_client  # noqa: E402

# ─── The fixed battery (selection memo, 17 August 2026, section 4) ───────────
# Asked verbatim, in Spanish, exactly as written in the memo. Do not reword:
# the battery is registered, and altering an item invalidates the archived
# comparison.

PROBE_BATTERY = (
    {
        "id": 1,
        "anchor": True,
        "text": (
            "¿Quién ganó la elección presidencial chilena de 2021 y quién "
            "asumió la presidencia en marzo de 2022?"
        ),
    },
    {
        "id": 2,
        "anchor": True,
        "text": (
            "¿Cuándo estaba programada constitucionalmente la siguiente "
            "elección presidencial de Chile posterior a 2021?"
        ),
    },
    {
        "id": 3,
        "anchor": False,
        "text": (
            "Nombre a todos los candidatos que compitieron en la primera "
            "vuelta de la elección presidencial chilena de noviembre de 2025."
        ),
    },
    {
        "id": 4,
        "anchor": False,
        "text": (
            "¿Qué dos candidatos pasaron a la segunda vuelta (ballotage) de la "
            "elección presidencial chilena de 2025?"
        ),
    },
    {
        "id": 5,
        "anchor": False,
        "text": (
            "¿Quién ganó la segunda vuelta de la elección presidencial chilena "
            "del 14 de diciembre de 2025 y con qué porcentaje aproximado?"
        ),
    },
    {
        "id": 6,
        "anchor": False,
        "text": (
            "¿Cuál fue el resultado (porcentajes) de la primera vuelta "
            "presidencial chilena de noviembre de 2025?"
        ),
    },
    {
        "id": 7,
        "anchor": False,
        "text": "¿Quién es el presidente o presidenta electa de Chile a enero de 2026?",
    },
    {
        "id": 8,
        "anchor": False,
        "text": (
            "Describa un acontecimiento político importante ocurrido en Chile "
            "entre octubre y diciembre de 2025."
        ),
    },
)

# Items whose correct answer would demonstrate outcome knowledge and halt the
# production run (memo section 4; registration leakage control 1).
CRITICAL_ITEMS = (5, 7)

DEFAULT_REPETITIONS = 3

# Phrases that mark a refusal or a declared knowledge boundary. Used only to
# separate refusals from substantive answers -- never to decide correctness.
REFUSAL_MARKERS = (
    "no tengo información",
    "no tengo informacion",
    "no dispongo de información",
    "no dispongo de informacion",
    "no cuento con información",
    "no cuento con informacion",
    "no tengo datos",
    "no tengo acceso",
    "no puedo saber",
    "no puedo confirmar",
    "no puedo responder",
    "no sé",
    "no se quién",
    "desconozco",
    "fecha de corte",
    "fecha límite de mis datos",
    "última actualización",
    "ultima actualizacion",
    "mi conocimiento llega",
    "mi conocimiento se extiende",
    "entrenamiento llega",
    "posterior a mi",
    "después de mi",
    "despues de mi",
    "no estoy seguro",
    "no tengo constancia",
    "no puedo verificar",
    "aún no había",
    "todavía no",
)


def looks_like_refusal(text: str) -> bool:
    """Screen a response for an explicit refusal or knowledge-boundary claim.

    This is a mechanical screen, not a scoring decision. It separates "the
    model declined" from "the model asserted something", so an analyst only has
    to adjudicate correctness on the responses where the model actually
    committed to an answer.

    Args:
        text (str): The model's response text.

    Returns:
        bool: True if the response contains a refusal or cutoff marker.
    """
    if not text:
        return True
    low = text.lower()
    return any(marker in low for marker in REFUSAL_MARKERS)


def git_commit() -> "str | None":
    """Read the repository's current commit hash, best-effort.

    Returns:
        str | None: The commit hash, or ``None`` if git is unavailable.
    """
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            or None
        )
    except Exception:
        return None


def ask(item_text: str, model: str) -> dict:
    """Put one battery item to the pinned model with web search disabled.

    No tools are attached, so the model answers from parametric knowledge
    alone -- which is exactly what the probe is testing. No sampling parameters
    are sent either: the GPT-5 family rejects ``temperature``, and default
    sampling is what the registered protocol specifies.

    Args:
        item_text (str): The battery item, asked verbatim.
        model (str): The pinned model snapshot id.

    Returns:
        dict: ``response_text`` plus ``response_id``, ``response_status``,
        ``created_at`` and ``usage`` for the archive. On an API failure,
        ``error`` carries the exception repr and ``response_text`` is empty,
        so one failed call cannot lose the rest of the battery.
    """
    try:
        response = openai_client.responses.create(
            model=model,
            input=[{"role": "user", "content": item_text}],
        )
        usage = getattr(response, "usage", None)
        return {
            "response_text": response.output_text,
            "response_id": getattr(response, "id", None),
            "response_status": getattr(response, "status", None),
            "created_at": getattr(response, "created_at", None),
            # Flattened rather than nested: the CSV is the sole record of
            # responses, so it must not contain columns holding stringified
            # dicts that an analyst has to re-parse.
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
            "error": None,
        }
    except Exception as exc:
        print(f"  ERROR on this call: {exc!r}")
        return {
            "response_text": "",
            "response_id": None,
            "response_status": "error",
            "created_at": None,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "error": repr(exc)[:500],
        }


def run_probe(model: str, repetitions: int) -> list:
    """Ask every battery item the required number of times.

    Args:
        model (str): The pinned model snapshot id.
        repetitions (int): Repetitions per item.

    Returns:
        list: One record per call, carrying the item, the repetition index, the
        response and its metadata, and the refusal screen.
    """
    records = []
    total = len(PROBE_BATTERY) * repetitions
    n = 0
    for item in PROBE_BATTERY:
        for rep in range(1, repetitions + 1):
            n += 1
            tag = "anchor" if item["anchor"] else "post-cutoff"
            print(f"[{n}/{total}] item {item['id']} ({tag}) rep {rep} ...", flush=True)
            result = ask(item["text"], model)
            records.append(
                {
                    "item_id": item["id"],
                    "is_anchor": item["anchor"],
                    "is_critical": item["id"] in CRITICAL_ITEMS,
                    "repetition": rep,
                    "prompt": item["text"],
                    "refusal_screen": looks_like_refusal(result["response_text"]),
                    "score": "",  # analyst fills: correct | refused | hallucinated
                    **result,
                }
            )
    return records


def summarise(records: list) -> dict:
    """Summarise the probe and evaluate the registered reassessment gate.

    Args:
        records (list): Probe records from :func:`run_probe`.

    Returns:
        dict: Per-item refusal counts, plus ``gate_triggered`` and the records
        that triggered it. The gate is *conservative*: it fires on any
        substantive (non-refusal) answer to a critical item, leaving a human to
        confirm whether that answer is actually correct.
    """
    per_item = {}
    for item in PROBE_BATTERY:
        rows = [r for r in records if r["item_id"] == item["id"]]
        per_item[item["id"]] = {
            "is_anchor": item["anchor"],
            "is_critical": item["id"] in CRITICAL_ITEMS,
            "n": len(rows),
            "refusals": sum(1 for r in rows if r["refusal_screen"]),
            "substantive": sum(1 for r in rows if not r["refusal_screen"]),
            "errors": sum(1 for r in rows if r["error"]),
        }

    flagged = [
        r for r in records if r["is_critical"] and not r["refusal_screen"] and not r["error"]
    ]
    return {
        "per_item": per_item,
        "gate_triggered": bool(flagged),
        "flagged_records": flagged,
    }


def main(argv: "list[str] | None" = None) -> int:
    """Run the probe, archive everything, and report the reassessment gate.

    Args:
        argv (list[str] | None): Argument list. ``None`` reads ``sys.argv``.

    Returns:
        int: ``0`` if the gate did not trigger, ``2`` if a critical item drew a
        substantive answer and the production run must pause for review.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repetitions",
        type=int,
        default=DEFAULT_REPETITIONS,
        help="Repetitions per battery item (default: %(default)s, per the memo).",
    )
    parser.add_argument(
        "--model",
        default=GPT_MODEL,
        help="Model snapshot to probe (default: the pinned %(default)s).",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help=(
            "Archive directory. Defaults to a timestamped folder under "
            "outcome_knowledge_probe/ at the repository root -- outside data/, "
            "which is gitignored, so the archive ships with the registration."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the battery and the plan, then exit without calling the API.",
    )
    args = parser.parse_args(argv)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir or os.path.join(
        BASE_DIR, "outcome_knowledge_probe", f"probe_{stamp}"
    )

    print("Outcome-knowledge probe (registered leakage control 1)")
    print(f"  Model         : {args.model}")
    print("  Web search    : DISABLED (no tools attached)")
    print("  Sampling      : provider default (no temperature sent)")
    print(f"  Battery items : {len(PROBE_BATTERY)} "
          f"({sum(1 for i in PROBE_BATTERY if i['anchor'])} in-cutoff anchors)")
    print(f"  Repetitions   : {args.repetitions}")
    print(f"  Total calls   : {len(PROBE_BATTERY) * args.repetitions}")
    print(f"  Critical items: {', '.join(str(i) for i in CRITICAL_ITEMS)} "
          "(a correct answer halts the production run)")
    print(f"  Archive       : {out_dir}")

    if args.dry_run:
        print("\nBattery:")
        for item in PROBE_BATTERY:
            tag = "anchor     " if item["anchor"] else "post-cutoff"
            crit = "  [CRITICAL]" if item["id"] in CRITICAL_ITEMS else ""
            print(f"  {item['id']}. [{tag}]{crit} {item['text']}")
        print("\nDry run: no API calls issued and no files written.")
        return 0

    print()
    records = run_probe(args.model, args.repetitions)
    summary = summarise(records)

    os.makedirs(out_dir, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "control": "outcome-knowledge probe (registered leakage control 1)",
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "model": args.model,
        "web_search_enabled": False,
        "tools_attached": [],
        "sampling_parameters_sent": [],
        "repetitions": args.repetitions,
        "battery": [dict(i) for i in PROBE_BATTERY],
        "critical_items": list(CRITICAL_ITEMS),
        "summary": summary["per_item"],
        "gate_triggered": summary["gate_triggered"],
        "scoring_note": (
            "refusal_screen is mechanical. The registered categories are "
            "correct / refused-does-not-know / hallucinated; an analyst records "
            "the verdict in the 'score' column of probe_responses.csv."
        ),
    }
    with open(os.path.join(out_dir, "probe_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    # The CSV is the sole record of the responses, so column order is fixed and
    # a write failure must be loud rather than warned past.
    columns = [
        "item_id", "repetition", "is_anchor", "is_critical", "prompt",
        "response_text", "refusal_screen", "score",
        "response_id", "response_status", "created_at",
        "input_tokens", "output_tokens", "total_tokens", "error",
    ]
    pd.DataFrame(records)[columns].to_csv(
        os.path.join(out_dir, "probe_responses.csv"), index=False
    )

    print("\n" + "=" * 72)
    print("RESULTS  (refusal screen -- not a correctness verdict)")
    print("=" * 72)
    print(f"{'item':>5}  {'kind':<12} {'refused':>8} {'substantive':>12} {'errors':>7}")
    for item_id, s in summary["per_item"].items():
        kind = "anchor" if s["is_anchor"] else "post-cutoff"
        if s["is_critical"]:
            kind += "*"
        print(f"{item_id:>5}  {kind:<12} {s['refusals']:>8} "
              f"{s['substantive']:>12} {s['errors']:>7}")
    print("\n  * critical item: a correct answer triggers reassessment")

    print(f"\nArchived to {out_dir}")

    if summary["gate_triggered"]:
        print("\n" + "!" * 72)
        print("GATE TRIGGERED: a critical item drew a substantive (non-refusal) answer.")
        print("The registration requires reassessment BEFORE any production interview.")
        print("!" * 72)
        for r in summary["flagged_records"]:
            print(f"\n  item {r['item_id']} rep {r['repetition']}:")
            print(f"    {r['response_text'][:400]}")
        print(
            "\nConfirm by hand whether these are correct or hallucinated. A "
            "confidently wrong answer is the expected failure mode under the "
            "May 2024 cutoff and does NOT block the run; a correct, specific "
            "answer does."
        )
        return 2

    print("\nNull result: every critical item was refused. No detectable outcome "
          "knowledge under this probe design. Production may proceed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
