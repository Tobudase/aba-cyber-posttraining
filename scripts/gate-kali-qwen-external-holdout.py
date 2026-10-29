#!/usr/bin/env python3
"""Read-only intake gate for a prospective external NL-to-command holdout.

This does not evaluate models, execute dataset commands, or access official TEST.
Passing it establishes provenance and obvious-overlap checks, not semantic gold.
"""

import argparse
import difflib
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PRIOR = [
    ROOT / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28/pilot_train.jsonl",
    ROOT / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28/pilot_dev.jsonl",
    ROOT / "data/benchkit/kali-qwen-confirmation-2026-10-28/dev93-private.jsonl",
]
MIN_ROWS = 32
MIN_TOOLS = 8


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value):
    return " ".join(re.findall(r"[a-z0-9_./:=-]+", value.casefold()))


def words(value):
    return set(re.findall(r"[a-z0-9_]+", normalize(value)))


def near(a, b):
    if not a or not b:
        return False
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    wa, wb = words(a), words(b)
    jaccard = len(wa & wb) / len(wa | wb) if wa | wb else 0
    return ratio >= 0.90 or (len(wa & wb) >= 5 and jaccard >= 0.85)


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def reference(row):
    native = row["native_label"]
    return normalize(native["query"]), normalize(native["ground_truth_command"])


def check(candidate_path):
    prior = []
    for path in PRIOR:
        for row in load_jsonl(path):
            assert row["source_official_split"].lower() == "train" and not row["official_test"]
            prior.append(reference(row))
    prior_questions = {q for q, _ in prior}
    prior_commands = {c for _, c in prior}
    rows = load_jsonl(candidate_path)
    issues = {}
    seen_id, seen_source, seen_q, seen_c = set(), set(), set(), set()
    tools = set()
    for index, row in enumerate(rows):
        key = str(row.get("id", index))
        errors = []
        required = ["id", "question", "gold_command", "tool", "source_dataset",
                    "source_record_id", "source_revision", "source_url", "license_spdx",
                    "evidence_url", "target_tool_version", "review"]
        missing = [field for field in required if field not in row or row[field] in (None, "")]
        if missing:
            issues[key] = ["missing_fields:" + ",".join(missing)]
            continue
        if any(not isinstance(row[f], str) for f in required if f != "review") or not isinstance(row["review"], dict):
            issues[key] = ["schema_type"]
            continue
        q, command = normalize(row["question"]), normalize(row["gold_command"])
        if not q or not command:
            errors.append("empty_normalized_content")
        if row["id"] in seen_id or (row["source_dataset"], row["source_record_id"]) in seen_source:
            errors.append("duplicate_id_or_source_record")
        if q in seen_q or command in seen_c:
            errors.append("duplicate_within_candidate")
        seen_id.add(row["id"])
        seen_source.add((row["source_dataset"], row["source_record_id"]))
        seen_q.add(q)
        seen_c.add(command)
        tools.add(row["tool"])
        if "kalibench" in row["source_dataset"].casefold() or row.get("official_test"):
            errors.append("not_external_or_official_test")
        if row["license_spdx"].casefold() in ("unknown", "none", ""):
            errors.append("license_unconfirmed")
        if row["target_tool_version"].casefold() in ("unknown", "pending", "unverified", "pending_version_review"):
            errors.append("tool_version_unverified")
        if any(urlparse(row[field]).scheme != "https" or not urlparse(row[field]).netloc
               for field in ("source_url", "evidence_url")):
            errors.append("missing_https_provenance")
        if q in prior_questions or command in prior_commands:
            errors.append("exact_prior_overlap")
        elif any(near(q, old_q) or near(command, old_command) for old_q, old_command in prior):
            errors.append("near_prior_overlap_review_required")
        review = row["review"]
        if (review.get("verdict") != "VALID" or review.get("reviewer_type") != "independent_human"
                or not review.get("reviewer_name") or not review.get("reviewed_at_utc")
                or not review.get("rationale")):
            errors.append("independent_review_missing")
        if errors:
            issues[key] = errors
    if len(rows) < MIN_ROWS:
        issues["__dataset__"] = issues.get("__dataset__", []) + ["too_few_rows"]
    if len(tools) < MIN_TOOLS:
        issues["__dataset__"] = issues.get("__dataset__", []) + ["too_few_tools"]
    return rows, issues, {"prior_files_sha256": {str(p.relative_to(ROOT)): sha(p) for p in PRIOR},
                          "candidate_sha256": sha(candidate_path), "rows": len(rows), "tools": len(tools),
                          "official_TEST_rows": 0, "model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true", help="Require all gates and operator attestation")
    parser.add_argument("--attestation", type=Path, help="JSON with no_model_queries_before_freeze=true")
    args = parser.parse_args()
    rows, issues, metadata = check(args.candidate)
    if args.freeze:
        if not args.attestation:
            issues["__attestation__"] = ["missing_operator_attestation"]
        else:
            attestation = json.loads(args.attestation.read_text())
            if (attestation.get("no_model_queries_before_freeze") is not True
                    or not attestation.get("operator_name") or not attestation.get("attested_at_utc")):
                issues["__attestation__"] = ["invalid_operator_attestation"]
            else:
                metadata["operator_attestation_sha256"] = sha(args.attestation)
    args.out.mkdir(parents=True, exist_ok=True)
    report = {"status": "FROZEN_SOURCE_SEPARATED_OPERATOR_ATTESTED" if args.freeze and not issues else "NOT_ADMITTED",
              **metadata, "issue_count": sum(len(v) for v in issues.values()), "issues_private": issues,
              "semantic_gold_certified_by_script": False,
              "pretraining_nonexposure_proven": False,
              "caveat": "Static provenance/overlap gate; source separation and attestations do not prove unseen pretraining or semantic correctness."}
    (args.out / "intake-report-private.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    if args.freeze and not issues:
        frozen = args.out / "frozen-holdout-private.jsonl"
        frozen.write_bytes(args.candidate.read_bytes())
        report["frozen_sha256"] = sha(frozen)
        (args.out / "frozen-manifest-private.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "rows", "tools", "issue_count", "official_TEST_rows", "model_calls")}, indent=2))
    if args.freeze and issues:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
