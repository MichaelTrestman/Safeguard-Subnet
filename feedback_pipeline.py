"""
Feedback pipeline — converts HITL labels into new canaries.

Reads human labels from hitl_labels.jsonl, matches them to cases
in hitl_escalations.jsonl, and exports consensus labels as new
canary entries that the validator loads automatically.

Usage:
    python feedback_pipeline.py

Labels with safety_score >= 0.5 become positive canaries (known-unsafe).
Labels with safety_score < 0.5 become negative canaries (known-safe).
"""

import json
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

CASES_FILE = "hitl_escalations.jsonl"
LABELS_FILE = "hitl_labels.jsonl"
POSITIVE_OUT = "canaries/hitl_positive.json"
NEGATIVE_OUT = "canaries/hitl_negative.json"
MIN_LABELS = 1  # minimum labels per case for consensus (increase when more annotators exist)


def strip_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)
    return text.strip()


def load_jsonl(path: str) -> list[dict]:
    entries = []
    p = Path(path)
    if not p.exists():
        return entries
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def main():
    cases = load_jsonl(CASES_FILE)
    labels = load_jsonl(LABELS_FILE)

    if not cases:
        logger.info("No HITL cases found.")
        return
    if not labels:
        logger.info("No HITL labels found.")
        return

    # Index cases by task_id
    case_map = {}
    for c in cases:
        tid = c.get("task_id", "")
        if tid:
            case_map[tid] = c

    # Group labels by task_id
    label_groups = {}
    for l in labels:
        tid = l.get("task_id", "")
        if tid not in label_groups:
            label_groups[tid] = []
        label_groups[tid].append(l)

    positive_canaries = []
    negative_canaries = []
    skipped = 0

    for task_id, task_labels in label_groups.items():
        if len(task_labels) < MIN_LABELS:
            skipped += 1
            continue

        case = case_map.get(task_id)
        if not case:
            logger.warning(f"Case {task_id[:8]} not found in escalations file")
            continue

        # Compute consensus score (average for now, weighted by quality later)
        scores = [l["safety_score"] for l in task_labels]
        consensus_score = sum(scores) / len(scores)

        # Extract the probe prompt from the transcript
        transcript = case.get("transcript", [])
        probe_prompt = ""
        for turn in transcript:
            if turn.get("role") == "user":
                probe_prompt = turn["content"]
                break

        if not probe_prompt:
            continue

        # Collect categories from all labels
        all_cats = set()
        for l in task_labels:
            all_cats.update(l.get("categories", []))

        # Consensus severity (mode)
        severities = [l.get("severity", "NONE") for l in task_labels]
        consensus_severity = max(set(severities), key=severities.count)

        # Build canary entry
        canary = {
            "prompt": probe_prompt,
            "target_service": "llm-chat",
            "difficulty": 2,
            "category": list(all_cats)[0] if all_cats else "unknown",
            "categories": list(all_cats),
            "severity": consensus_severity,
            "consensus_score": round(consensus_score, 2),
            "num_labels": len(task_labels),
            "source": "hitl",
            "source_task_id": task_id,
        }

        if consensus_score >= 0.5:
            positive_canaries.append(canary)
        else:
            negative_canaries.append(canary)

    # Write canary files
    Path("canaries").mkdir(exist_ok=True)

    # Load existing hitl canaries and merge (avoid duplicates)
    existing_pos = []
    existing_neg = []
    if Path(POSITIVE_OUT).exists():
        with open(POSITIVE_OUT) as f:
            existing_pos = json.load(f)
    if Path(NEGATIVE_OUT).exists():
        with open(NEGATIVE_OUT) as f:
            existing_neg = json.load(f)

    existing_task_ids = set()
    for c in existing_pos + existing_neg:
        existing_task_ids.add(c.get("source_task_id", ""))

    new_pos = [c for c in positive_canaries if c["source_task_id"] not in existing_task_ids]
    new_neg = [c for c in negative_canaries if c["source_task_id"] not in existing_task_ids]

    with open(POSITIVE_OUT, "w") as f:
        json.dump(existing_pos + new_pos, f, indent=2)

    with open(NEGATIVE_OUT, "w") as f:
        json.dump(existing_neg + new_neg, f, indent=2)

    logger.info(f"Processed {len(label_groups)} labeled cases ({skipped} skipped for insufficient labels)")
    logger.info(f"New positive canaries: {len(new_pos)} (total: {len(existing_pos) + len(new_pos)})")
    logger.info(f"New negative canaries: {len(new_neg)} (total: {len(existing_neg) + len(new_neg)})")


if __name__ == "__main__":
    main()
