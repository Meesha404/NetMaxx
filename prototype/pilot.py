#!/usr/bin/env python3
"""Offline pilot preflight, founder review export, and quality measurements."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys

import event_router as er

LABELS = ("identity_correct", "useful_to_meet", "icebreaker_supported")


def preflight(path, icp_path=None):
    rows, rejected, total = er.ingest(path)
    icp = er.load_icp(icp_path)
    return {"network_calls": 0, "input_rows": total, "unique_valid_attendees": len(rows),
            "invalid_rows": len(rejected), "pilot_size_ok": 2 <= len(rows) <= 30,
            "credentials_present": {k: bool(os.environ.get(k)) for k in ("PDL_API_KEY", "OPENAI_API_KEY", "APIFY_TOKEN")},
            "target": icp["target"], "requester": icp["requester"],
            "ready_for_core_smoke": bool(rows) and not rejected and all(os.environ.get(k) for k in ("PDL_API_KEY", "OPENAI_API_KEY")),
            "note": "Presence only; account access, credits and the event objective need confirmation before live use."}


def records(matrix):
    return matrix["ranked_attendees"] + [r for r in matrix["review_and_errors"] if "attendee_id" in r]


def review_template(matrix):
    top = matrix["top_candidate_ids"]
    return {"output_digest": er.digest(matrix), "run_id": matrix.get("run_id"), "mode": matrix["mode"],
            "instructions": "Set labels to true, false or null (unknown/unreviewed). Inspect linked identity and evidence. Record reviewer and notes. Do not replace null with false for missing evidence.",
            "attendees": [{"attendee_id": r["attendee_id"], "name": r[er.HEADERS[0]],
                "company": r[er.HEADERS[1]], "status": r["status"], "score": r.get("score"),
                "shortlist_position": top.index(r["attendee_id"]) + 1 if r["attendee_id"] in top else None,
                "identity": r.get("identity"), "reason": r.get("reason_for_priority"),
                "icebreaker": r.get("icebreaker_hook"), "evidence": r.get("evidence", []),
                "data_gaps": r.get("data_gaps", []), "error": r.get("error"),
                **{label: None for label in LABELS}, "reviewer": "", "notes": ""} for r in records(matrix)]}


def fraction(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "fraction": numerator / denominator if denominator else None}


def summarize(matrix, review=None):
    rows = records(matrix)
    by_id = {r["attendee_id"]: r for r in rows}
    labels = {}
    if review is not None:
        if review.get("output_digest") != er.digest(matrix):
            raise er.PipelineError("review_belongs_to_different_output")
        for item in review.get("attendees", []):
            identifier = item.get("attendee_id")
            if identifier not in by_id or identifier in labels:
                raise er.PipelineError("review_unknown_or_duplicate_attendee")
            if any(item.get(k) is not None and type(item[k]) is not bool for k in LABELS):
                raise er.PipelineError("review_labels_must_be_boolean_or_null")
            if any(item.get(k) is not None for k in LABELS) and not item.get("reviewer", "").strip():
                raise er.PipelineError("reviewer_required_for_judgments")
            labels[identifier] = item
    attempted = [r for r in rows if r["status"] not in {"not_processed", "not_processed_limit"}]
    resolved = [r for r in attempted if (r.get("identity") or {}).get("status") == "high_confidence_match"]
    top = matrix["top_candidate_ids"]
    quality = {}
    for k in (5, 10):
        selected = top[:k]
        judged = [labels[x] for x in selected if x in labels and labels[x].get("useful_to_meet") is not None]
        quality[f"top_{k}"] = {"available_candidates": len(selected), "reviewed": len(judged),
            "useful_among_reviewed": fraction(sum(r["useful_to_meet"] for r in judged), len(judged)),
            "confirmed_useful_among_available": fraction(sum(r["useful_to_meet"] for r in judged), len(selected)),
            "unreviewed": len(selected) - len(judged)}
    identity_labels = [labels[r["attendee_id"]]["identity_correct"] for r in resolved
                       if r["attendee_id"] in labels and labels[r["attendee_id"]].get("identity_correct") is not None]
    hooks = [labels[r["attendee_id"]]["icebreaker_supported"] for r in rows
             if r.get("icebreaker_hook") and r["attendee_id"] in labels
             and labels[r["attendee_id"]].get("icebreaker_supported") is not None]
    return {"mode": matrix["mode"], "run_id": matrix.get("run_id"), "run_status": matrix["run_status"],
        "input_rows": matrix["input_rows"], "unique_valid_attendees": len(rows), "attempted_unique_attendees": len(attempted),
        "invalid_input_rows": sum(r["status"] == "invalid_input" for r in matrix["review_and_errors"]),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "resolved_coverage": fraction(len(resolved), len(attempted)),
        "review_coverage": fraction(sum(r["status"] in {"needs_review", "unresolved"} for r in attempted), len(attempted)),
        "error_coverage": fraction(sum(r["status"] == "error" for r in attempted), len(attempted)),
        "identity_accuracy_among_reviewed_resolved": fraction(sum(identity_labels), len(identity_labels)),
        "unsupported_hooks_among_reviewed": fraction(sum(not x for x in hooks), len(hooks)),
        "shortlist_quality": quality, "runtime_seconds": matrix.get("runtime_seconds"),
        "provider_usage": matrix.get("provider_usage", {}),
        "openai_tokens_observed_this_run": matrix.get("openai_tokens_observed_this_run", {}),
        "notes": ["Coverage denominator: attempted unique input triples, including fatal attempted rows; invalid and unprocessed rows excluded.",
                  "Resolved coverage may overlap errors when scoring failed after resolution. Shortlist is distinct LinkedIn identities.",
                  "Unreviewed labels remain unknown; synthetic demo metrics do not measure live quality.",
                  "Request attempts include retries; observed token counts exclude cached assessments and unknown usage on failed responses. No monetary cost inferred."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("input", type=Path)
    pre.add_argument("--icp", type=Path)
    export = sub.add_parser("review")
    export.add_argument("input", type=Path)
    export.add_argument("--output", type=Path, required=True)
    summary = sub.add_parser("summarize")
    summary.add_argument("input", type=Path)
    summary.add_argument("--review", type=Path)
    summary.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            print(json.dumps(preflight(args.input, args.icp), indent=2))
            return 0
        # Preserve existing human labels, sources and earlier metrics.
        if args.output.exists():
            raise er.PipelineError("output_exists_choose_new_path")
        matrix = json.loads(args.input.read_text())
        result = review_template(matrix) if args.command == "review" else summarize(
            matrix, json.loads(args.review.read_text()) if args.review else None)
        er.atomic_json(args.output, result)
        return 0
    except (er.PipelineError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(str(exc) if isinstance(exc, er.PipelineError) else type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
