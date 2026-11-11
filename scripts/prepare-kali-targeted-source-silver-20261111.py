#!/usr/bin/env python3
"""Build a source-pinned, training-only Kali CLI coverage supplement.

The new examples deliberately target tools diagnosed on an exposed DEV set.
Consequently that set can only be used for debugging, never as independent
evidence that this supplement improves generalization.
"""

from collections import Counter
import hashlib
import importlib.util
import json
import re
import shlex

from benchkit import (ARTIFACT, ROOT, artifact_spec, kali_prompts, load_jsonl,
                      native_kali, row_fingerprint, sha, strict_option_values,
                      validate_dataset, write_json, write_jsonl)
from kali_targeted_source_silver_tasks import recipes


def main():
    spec = importlib.util.spec_from_file_location("domain", ROOT / "scripts/prepare-kali-domain-dev.py")
    domain = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(domain)
    source = ARTIFACT / "kali" / domain.DOC_REL
    assert sha(source.read_bytes()) == domain.DOC_SHA
    docs = load_jsonl(source)
    original = load_jsonl(ARTIFACT / "kali/KaliBench_data/kalibench_verified_train_3504.jsonl")
    norm_cmd = lambda s: " ".join(shlex.split(s))
    norm_query = lambda s: " ".join(s.casefold().split())
    blocked_commands = {norm_cmd(r["ground_truth_command"]) for r in original}
    blocked_queries = {norm_query(r["query"]) for r in original}
    raw, reviews = [], []
    for recipe in recipes():
        matches = [d for d in docs if d["subtool"] == recipe["tool"]]
        assert len(matches) == 1, (recipe["tool"], len(matches))
        doc = matches[0]
        assert doc["title"] not in domain.RESERVED_PACKAGES
        help_text = doc["usage_code"].split("```", 1)[0]
        for variant, values in enumerate(recipe["variants"], 1):
            row = {k: (v.format(**values) if isinstance(v, str) else v)
                   for k, v in recipe.items() if k in {"tool", "query", "command"}}
            row["optional_args"] = {k: v.format(**values) if v is not None else None
                                    for k, v in recipe["optional_args"].items()}
            row["positional_args"] = [v.format(**values) for v in recipe["positional_args"]]
            domain.validate_command(row, help_text)
            for group in row["optional_args"]:
                for alias in group.split("|"):
                    assert re.search(r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", help_text), alias
            assert norm_cmd(row["command"]) not in blocked_commands
            assert norm_query(row["query"]) not in blocked_queries
            identifier = f"kali-targeted-silver-{recipe['family']}-{variant}"
            raw.append({"custom_id": identifier, "query": row["query"],
                        "tool_name": row["tool"], "ground_truth_command": row["command"],
                        "optional_args": row["optional_args"], "positional_args": row["positional_args"]})
            reviews.append({"id": identifier, "tool": row["tool"], "family": recipe["family"],
                            "package": doc["title"], "source_row": doc["source_row"],
                            "source_help_sha256": hashlib.sha256(help_text.encode()).hexdigest(),
                            "literal_options_and_values_checked": True,
                            "publisher_verified": False, "terminal_verified": False,
                            "independent_expert_review": False})
    assert len(raw) == len({r["custom_id"] for r in raw}) == 16
    assert len({norm_cmd(r["ground_truth_command"]) for r in raw}) == 16
    assert len({norm_query(r["query"]) for r in raw}) == 16
    prompts, labels = kali_prompts(raw)
    scorer = native_kali()
    by_id = {r["id"]: r for r in reviews}
    rows = []
    for item in raw:
        identifier = item["custom_id"]
        target = "<output>\n" + item["ground_truth_command"] + "\n</output>"
        assert scorer.score_one(labels[identifier], target)["exact_match"] == 1, identifier
        assert strict_option_values(labels[identifier], target, scorer), identifier
        review = by_id[identifier]
        rows.append({"id": identifier, "benchmark": "kali", "task": "unrestricted",
                     "split": "train", "training_eligible": True, "official_test": False,
                     "self_authored": True, "messages": prompts[identifier], "target": target,
                     "native_label": labels[identifier],
                     "group_id": "targeted-source-silver:" + review["family"],
                     "template_family": review["family"], "tool_package": review["package"],
                     "source_row": review["source_row"], "source_url": domain.URL,
                     "source_sha256": domain.DOC_SHA,
                     "quality": "AI_AUTHORED_SOURCE_SILVER_NO_TERMINAL_OR_EXPERT_VERIFICATION",
                     "input_sha256": row_fingerprint(prompts[identifier])})
    validate_dataset(rows, "train", "kali")
    out = ROOT / "data/benchkit/kali-targeted-source-silver-2026-11-11"
    assert not out.exists(), "Frozen training supplement must not be replaced"
    out.mkdir(parents=True)
    write_jsonl(out / "train.jsonl", rows)
    manifest = {"schema": "benchkit.dataset.v1", "benchmark": "kali",
                "official_test": False, "splits": {"train": artifact_spec(out / "train.jsonl", rows)},
                "source_sha256": domain.DOC_SHA,
                "recipes_sha256": sha((ROOT / "scripts/kali_targeted_source_silver_tasks.py").read_bytes()),
                "quality": "source-silver, training-only",
                "exposed_DEV_adaptive": True,
                "limitations": ["Model-error-guided tool selection; exposed DEV cannot independently validate this supplement.",
                                "Help text and native gold echo validate syntax, not task semantics or terminal behavior.",
                                "No publisher verification, command execution, or independent expert review.",
                                "No official TEST or sealed final64 used."]}
    write_json(out / "manifest.json", manifest)
    audit = {"status": "TRAIN_ONLY_SOURCE_SILVER_PREPARED_NOT_APPROVED_FOR_MODEL_PROMOTION",
             "rows": len(rows), "families": len({r["template_family"] for r in rows}),
             "tools": dict(Counter(r["native_label"]["tool_name"] for r in rows)),
             "source_sha256": domain.DOC_SHA,
             "train_sha256": sha((out / "train.jsonl").read_bytes()),
             "official_train_command_overlap": 0, "official_train_query_overlap": 0,
             "native_gold_echo_failures": 0,
             "commands_executed": 0, "official_TEST_rows_read": 0,
             "sealed_final64_rows_read": 0, "exposed_DEV_adaptive": True,
             "publisher_verified": False, "terminal_verified": False,
             "independent_expert_review": False, "reviews": reviews}
    write_json(out / "audit.json", audit)
    print(json.dumps({k: v for k, v in audit.items() if k != "reviews"}, indent=2))


if __name__ == "__main__":
    main()
