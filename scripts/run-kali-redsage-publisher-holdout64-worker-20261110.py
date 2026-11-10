#!/usr/bin/env python3
"""Inference-only publisher-TRAIN internal holdout with matched C13 wrapper."""

import base64
import concurrent.futures
import gzip
import hashlib
import json
import tarfile
import sys
import time
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    started = time.monotonic()
    protocol = json.loads(Path("/input/protocol.json").read_text())
    assert protocol["status"] == "FROZEN_REDSAGE_PUBLISHER_TRAIN_HOLDOUT64_BEFORE_OUTPUTS"
    assert protocol["official_TEST_rows"] == protocol["optimizer_steps"] == 0
    assert protocol["model_promotion_allowed"] is False
    assert sha("/input/worker.py") == protocol["worker_sha256"]
    raw = gzip.decompress(Path("/input/inputs.json.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == protocol["inputs_sha256"]
    payload = json.loads(raw)
    assert len(payload["holdout"]) == 64 and len(payload["anchors"]) == 4
    assert len({r["id"] for r in payload["holdout"] + payload["anchors"]}) == 68
    assert all(set(r) == {"id", "native_messages"} for r in payload["holdout"])
    assert all(set(r) == {"id", "native_messages", "expected_sha256"} for r in payload["anchors"])
    model_dir = Path("/scratch/model")
    model_dir.mkdir()

    def stage(item):
        name, expected = item
        assert Path(name).name == name
        src, dst = Path("/cache/model") / name, model_dir / name
        digest = hashlib.sha256()
        with src.open("rb") as incoming, dst.open("xb") as outgoing:
            for block in iter(lambda: incoming.read(8 * 1024**2), b""):
                digest.update(block)
                outgoing.write(block)
        assert digest.hexdigest() == expected
        print("STAGED " + name, flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(stage, protocol["checkpoint_files"].items()))
    assert sha("/cache/runtime-deps.tar") == protocol["runtime_archive_sha256"]
    deps = Path("/scratch/deps")
    deps.mkdir()
    with tarfile.open("/cache/runtime-deps.tar") as archive:
        assert all(member.isfile() and (deps / member.name).resolve().is_relative_to(deps.resolve())
                   for member in archive.getmembers())
        archive.extractall(deps, filter="data")
    sys.path.insert(0, str(deps))
    print("DEPENDENCIES_READY", flush=True)

    import torch
    from importlib.metadata import version
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model, set_peft_model_state_dict
    from safetensors.torch import load_file

    assert {name: version(name) for name in protocol["expected_packages"]} == protocol["expected_packages"]
    assert torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0)
    assert gpu_name in protocol["allowed_GPU_models"]
    torch.set_num_threads(2)
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True,
                    trust_remote_code=False, fix_mistral_regex=False)
    tokenizer.padding_side = "left"
    tokenizer.pad_token = tokenizer.eos_token
    torch.manual_seed(protocol["initialization_seed"])
    base = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True,
                    device_map={"": 0}, torch_dtype=torch.bfloat16, attn_implementation="sdpa")
    base.requires_grad_(False)
    base.enable_input_require_grads()
    model = get_peft_model(base, LoraConfig(**protocol["LoRA_config"]))
    model.eval()
    adapter = Path("/cache") / protocol["adapter_path"]
    assert adapter.resolve().is_relative_to(Path("/cache").resolve())
    assert sha(adapter / "adapter_model.safetensors") == protocol["adapter_sha256"]
    print("MODEL_LOADED", flush=True)

    def infer(active, rows, arm, label):
        out = []
        for offset in range(0, len(rows), protocol["batch_size"]):
            batch = rows[offset:offset + protocol["batch_size"]]
            prompts = [tokenizer.apply_chat_template(row["native_messages"], tokenize=False,
                        add_generation_prompt=True) for row in batch]
            assert all(prompt.endswith("<think>") for prompt in prompts)
            inputs = tokenizer(prompts, padding=True, add_special_tokens=False,
                               return_tensors="pt").to("cuda")
            torch.manual_seed(protocol["inference_seed"])
            with torch.inference_mode():
                generated = active.generate(**inputs, max_new_tokens=protocol["max_new_tokens"],
                    do_sample=False, use_cache=True, pad_token_id=tokenizer.eos_token_id,
                    eos_token_id=tokenizer.eos_token_id, temperature=None, top_p=None, top_k=None)
            for row, ids in zip(batch, generated[:, inputs["input_ids"].shape[1]:].tolist()):
                truncated = tokenizer.eos_token_id not in ids
                effective = ids if truncated else ids[:ids.index(tokenizer.eos_token_id)]
                response = tokenizer.decode(effective, skip_special_tokens=False,
                                            clean_up_tokenization_spaces=False)
                if label == "anchor":
                    expected = row["expected_sha256"][arm]
                    actual = hashlib.sha256(response.encode()).hexdigest()
                    assert actual == expected, "Historical anchor mismatch: " + arm + " " + row["id"]
                out.append({"id": row["id"], "arm": arm, "response": response,
                            "truncated": truncated, "generated_tokens": len(effective)})
            print("INFER " + arm + " " + label + " " + str(len(out)) + "/" + str(len(rows)), flush=True)
        return out

    for arm in ("base", "sft"):
        if arm == "sft":
            state = load_file(str(adapter / "adapter_model.safetensors"))
            set_peft_model_state_dict(model, state, adapter_name="default")
            model.eval()
        infer(model, payload["anchors"], arm, "anchor")
        predictions = infer(model, payload["holdout"], arm, "holdout")
        packed = base64.b64encode(gzip.compress(json.dumps(predictions, ensure_ascii=False).encode())).decode()
        print("PUBLISHER_HOLDOUT64_PREDICTIONS_" + arm.upper() + "=" + packed, flush=True)
    receipt = {"status": "COMPLETE_REDSAGE_PUBLISHER_TRAIN_HOLDOUT64", "GPU": gpu_name,
               "GPU_count": 1, "source_rows": 64, "historical_anchors_passed": 8,
               "protocol_sha256": sha("/input/protocol.json"),
               "worker_sha256": sha("/input/worker.py"), "optimizer_steps": 0,
               "official_TEST_rows": 0, "model_promotion_allowed": False,
               "wall_seconds": round(time.monotonic() - started, 2),
               "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated()}
    print("EXTERNAL26_RECEIPT=" + json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
