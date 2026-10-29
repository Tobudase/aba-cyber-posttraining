#!/usr/bin/env python3
"""Assemble private, source-linked review cases without claiming human approval."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AI = ROOT / "data/benchkit/kali-qwen-ai-review-2026-10-29"
DEV = ROOT / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28/pilot_dev.jsonl"
COMPARISON = AI / "gpu-cycle/comparison-private.json"
LEDGER = AI / "ai-review-ledger-private.json"
OUT = AI / "next-review"

CASE_SOURCES = {
    "pm3": "https://www.kali.org/tools/proxmark3/",
    "radcrypt": "https://www.kali.org/tools/freeradius/",
    "showmount": "https://www.kali.org/tools/nfs-utils/",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def main():
    ledger = json.loads(LEDGER.read_text())
    dev = {r["id"]: r for r in (json.loads(s) for s in DEV.read_text().splitlines() if s)}
    changed = json.loads(COMPARISON.read_text())["discordant_cases"]
    assert len(ledger) == 512 and len(changed) == 3 and len(dev) == 128
    assert all(r["source_official_split"].lower() == "train" and not r["official_test"] for r in dev.values())

    urgent = []
    followup = []
    for r in ledger:
        status = r["ai_review_status"]
        if status not in {"AI_QUARANTINE_SOURCE_CONFLICT", "AI_ENVIRONMENT_CONFOUNDED_UNRESOLVED"}:
            continue
        case = {
            "case_key": "train:" + r["id"],
            "source_official_split": "TRAIN",
            "question": r["question"],
            "publisher_reference": r["gold_command"],
            "tool": r["tool"],
            "receipt_cues": r["receipt_cues"],
            "ai_triage_status": status,
            "ai_triage_rationale": r["ai_review_rationale"],
            "documentation_url": r["source_evidence_url"],
            "requested_decision": "Does the command satisfy the requested effect on the target tool version?",
        }
        (urgent if status == "AI_QUARANTINE_SOURCE_CONFLICT" else followup).append(case)

    for r in changed:
        source = dev[r["id"]]
        tool = source["native_label"]["tool_name"]
        assert tool == r["tool"] and tool in CASE_SOURCES
        urgent.append({
            "case_key": "dev:" + r["id"],
            "source_official_split": "TRAIN_internal_DEV",
            "question": source["native_label"]["query"],
            "publisher_reference": r["publisher_gold"],
            "original512_prediction": r["original_response"],
            "ai_review505_prediction": r["ai_review_response"],
            "automatic_comparison_state": r["comparison_state"],
            "tool": tool,
            "documentation_url": CASE_SOURCES[tool],
            "requested_decision": "Are both model commands valid for the exact task wording and tool version?",
        })

    assert len(urgent) == 10 and len(followup) == 42
    cases = sorted(urgent, key=lambda r: r["case_key"]) + sorted(followup, key=lambda r: r["case_key"])
    assert len({r["case_key"] for r in cases}) == 52
    OUT.mkdir(parents=True, exist_ok=True)
    packet = {
        "status": "PRIVATE_AI_TRIAGE_AWAITING_INDEPENDENT_REVIEW",
        "source_sha256": {"ai_ledger": sha(LEDGER), "internal_dev128": sha(DEV), "comparison": sha(COMPARISON)},
        "priority_cases": 10,
        "followup_cases": 42,
        "official_TEST_rows": 0,
        "independent_human_signoffs": 0,
        "cases": cases,
    }
    packet_path = OUT / "case-packet-private.json"
    dump(packet_path, packet)
    form = {
        "status": "BLANK_INDEPENDENT_REVIEW_FORM",
        "case_packet_sha256": sha(packet_path),
        "reviewer_name": None,
        "reviewer_affiliation": None,
        "reviewed_at_utc": None,
        "instructions": "Read each task, reference, documentation and target tool version. Do not run commands on live systems. Record VALID, INVALID or UNCLEAR, evidence and rationale. AI triage is not human adjudication. Do not change frozen automatic scores.",
        "allowed_verdicts": ["VALID", "INVALID", "UNCLEAR"],
        "cases": [{"case_key": r["case_key"], "tool": r["tool"], "verdict": None,
                   "target_tool_version": None, "evidence_url_or_disposable_fixture": None,
                   "rationale": None} for r in cases],
    }
    dump(OUT / "independent-review-form-private.json", form)
    summary = {"status": packet["status"], "priority_cases": 10, "followup_cases": 42,
               "total_cases": 52, "packet_sha256": sha(packet_path), "review_form_sha256": sha(OUT / "independent-review-form-private.json"),
               "official_TEST_rows": 0, "human_signoffs": 0}
    dump(OUT / "summary-private.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
