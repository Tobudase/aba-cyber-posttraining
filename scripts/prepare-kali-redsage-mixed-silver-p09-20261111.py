#!/usr/bin/env python3
"""Freeze one 733 publisher + 16 source-silver matched SFT pilot, without inference."""

import datetime
import gzip
import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer
from kali_mixed_source_silver_sft_recipe import validate_recipe


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "data/benchkit/kali-redsage-aba-publisher-v2-2026-11-10"
P07 = STUDY / "P07"
OUT = STUDY / "P09"
SOURCE = ROOT / "data/benchkit/kali-targeted-source-silver-2026-11-11"
WORKER = ROOT / "scripts/run-kali-redsage-mixed-silver-worker-20261111.py"
RECIPE = ROOT / "scripts/kali_mixed_source_silver_sft_recipe.py"
TOKENIZER = ROOT / ".tools/model-tokenizer/redsage-k-843e2e3096e7"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    assert not OUT.exists(), "Never replace a frozen or attempted candidate"
    p07 = json.loads(gzip.decompress((P07 / "payload-private.json.gz").read_bytes()))
    old = p07["train_rows"]
    assert len(old) == 733 and all(r["publisher_terminal_PASS_EXECUTED"] is True and
                                   r["publisher_model_ACCURATE"] is True for r in old)
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    assert manifest["exposed_DEV_adaptive"] is True
    assert manifest["quality"] == "source-silver, training-only"
    assert sha(SOURCE / "train.jsonl") == manifest["splits"]["train"]["sha256"]
    new = [json.loads(line) for line in (SOURCE / "train.jsonl").read_text().splitlines()]
    assert len(new) == 16 and all(r["quality"] ==
                                  "AI_AUTHORED_SOURCE_SILVER_NO_TERMINAL_OR_EXPERT_VERIFICATION"
                                  for r in new)
    ids = {r["id"] for r in old}
    protected = {r["id"] for r in p07["dev1"] + p07["dev2"] + p07["anchors"]}
    assert len(ids) == 733 and not ids & protected
    assert not {r["id"] for r in new} & (ids | protected)
    tok = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True,
                                         trust_remote_code=False, fix_mistral_regex=False)
    assert tok.eos_token_id == 151645 and tok.eos_token == "<|im_end|>"
    extra = []
    for r in new:
        prompt = tok.apply_chat_template(r["messages"], tokenize=False, add_generation_prompt=True)
        assert prompt.endswith("<think>")
        completion = "\n</think>\n\n" + r["target"]
        prompt_ids = tok.encode(prompt, add_special_tokens=False)
        target_ids = tok.encode(completion, add_special_tokens=False)
        sequence = prompt_ids + target_ids + [tok.eos_token_id]
        assert len(sequence) <= 2048
        assert tok.decode(sequence, skip_special_tokens=False,
                          clean_up_tokenization_spaces=False) == prompt + completion + tok.eos_token
        extra.append({"id": r["id"], "split": "train", "training_eligible": True,
                      "official_test": False, "publisher_terminal_PASS_EXECUTED": False,
                      "publisher_model_ACCURATE": False, "source_silver": True,
                      "input_ids": sequence,
                      "labels": [-100] * len(prompt_ids) + target_ids + [tok.eos_token_id],
                      "prompt_tokens": len(prompt_ids), "target_tokens": len(target_ids) + 1})
    rows = old + extra
    prior = json.loads((P07 / "protocol-private.json").read_text())
    protocol = dict(prior)
    optimizer = dict(protocol["optimizer"])
    optimizer["max_optimizer_steps"] = len(rows)
    validate_recipe(optimizer, rows)
    protocol.update({"candidate_id": "P09", "candidate_recipe": {
        "rows": "publisher733_plus_source_silver16", "lr": 1e-5, "seed": 42},
        "training_rows": len(rows), "optimizer": optimizer,
        "worker_sha256": sha(WORKER), "recipe_sha256": sha(RECIPE),
        "source_silver_rows": 16, "publisher_verified_rows": 733,
        "source_silver_train_sha256": sha(SOURCE / "train.jsonl"),
        "exposed_DEV_adaptive": True, "publisher_only": False,
        "model_promotion_allowed": False, "official_TEST_rows": 0,
        "scope": "Prospective matched operator pilot; 16 AI-authored source-silver rows; exposed TRAIN-source DEV for diagnostics only"})
    raw = json.dumps({"train_rows": rows, "dev1": p07["dev1"], "dev2": p07["dev2"],
                      "anchors": p07["anchors"]}, ensure_ascii=False, separators=(",", ":")).encode()
    packed = gzip.compress(raw, mtime=0)
    protocol["payload_sha256"] = hashlib.sha256(raw).hexdigest()
    protocol["payload_gzip_sha256"] = hashlib.sha256(packed).hexdigest()
    protocol["prepared_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    OUT.mkdir(parents=True)
    (OUT / "payload-private.json.gz").write_bytes(packed)
    dump(OUT / "train-encoded-private.json", rows)
    dump(OUT / "protocol-private.json", protocol)
    freeze = {"status": "MIXED_SOURCE_SILVER_OPERATOR_PILOT_FROZEN_BEFORE_OUTPUTS",
              "candidate_id": "P09", "matched_control": "P07", "training_rows": len(rows),
              "publisher_verified_rows": 733, "source_silver_rows": 16,
              "silver_terminal_verified": False, "silver_expert_reviewed": False,
              "exposed_DEV_adaptive": True, "official_TEST_rows": 0,
              "sealed_final64_used": False, "model_promotion_allowed": False,
              "selection_note": "P09 is operator-designed and is not ABA-selected",
              "source_silver_train_sha256": sha(SOURCE / "train.jsonl"),
              "p07_payload_sha256": sha(P07 / "payload-private.json.gz"),
              "protocol_sha256": sha(OUT / "protocol-private.json"),
              "payload_gzip_sha256": sha(OUT / "payload-private.json.gz"),
              "worker_sha256": sha(WORKER), "recipe_sha256": sha(RECIPE),
              "decision_rule": "Diagnostic only. No promotion from exposed DEV; retain E0 until a separately frozen independent evaluation."}
    dump(OUT / "freeze-manifest-private.json", freeze)
    print(json.dumps({"status": freeze["status"], "candidate": "P09",
                      "training_rows": len(rows), "publisher_verified": 733,
                      "source_silver": 16, "official_TEST_rows": 0,
                      "protocol_sha256": freeze["protocol_sha256"]}))


if __name__ == "__main__":
    main()
