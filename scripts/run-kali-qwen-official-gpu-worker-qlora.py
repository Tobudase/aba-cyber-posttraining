"""One bounded, publisher-TRAIN-only Qwen baseline/SFT/DEV worker.

Runs inside a reviewed one-GPU Kubernetes Job. Dataset commands remain inert text.
No official TEST or development references enter this process.
"""

import base64
import gzip
import hashlib
import json
import math
import os
import random
import sys
import tarfile
import time
from pathlib import Path


ROOT = Path("/model-cache/qwen3-8b-b968826d9c46")
INPUT = Path("/input")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unpack(name, expected):
    raw = base64.b64decode((INPUT / name).read_text(), validate=True)
    data = gzip.decompress(raw)
    assert sha(data) == expected
    return json.loads(data)


def load_deps(archive, expected):
    assert digest(archive) == expected
    destination = Path("/scratch/deps")
    destination.mkdir()
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if not member.isfile() or not (destination / member.name).resolve().is_relative_to(destination.resolve()):
                raise ValueError("Unsafe dependency archive member")
        tar.extractall(destination, filter="data")
    sys.path.insert(0, str(destination))


def main():
    started = time.monotonic()
    protocol = json.loads((INPUT / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_GPU_MODEL_OUTPUTS"
    assert protocol["precision"] == "NF4_QLORA_BF16_COMPUTE"
    assert protocol["official_test_rows"] == 0 and protocol["development_gradient_rows"] == 0
    assert protocol["model_id"] == "Qwen/Qwen3-8B"
    assert protocol["model_revision"] == "b968826d9c46dd6066d109eabc6255188de91218"
    assert digest(INPUT / "worker.py") == protocol["worker_sha256"]
    train = unpack("train.json.gz.b64", protocol["train_encoded_sha256"])
    dev = unpack("dev.json.gz.b64", protocol["dev_inputs_sha256"])
    assert len(train) == 512 and len(dev) == 128
    assert {r["id"] for r in train}.isdisjoint(r["id"] for r in dev)
    assert all(r["official_test"] is False and r["publisher_verified_silver"] is True for r in train)
    assert all(r["official_test"] is False and set(r).isdisjoint({"target", "native_label", "ground_truth_command"}) for r in dev)
    for record in train:
        cut = record["prompt_tokens"]
        assert record["labels"][:cut] == [-100] * cut
        assert record["labels"][cut:] == record["input_ids"][cut:]
        assert len(record["input_ids"]) <= 2048
    prefetch = json.loads((ROOT / "prefetch-receipt.json").read_text())
    assert prefetch["status"] == "COMPLETE_CPU_ONLY" and prefetch["GPU_requested"] == 0
    assert prefetch["revision"] == protocol["model_revision"]
    assert prefetch["sha256"] == protocol["checkpoint_sha256"]
    for name, expected in protocol["checkpoint_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Pinned checkpoint hash changed: " + name)
    load_deps(Path("/deps-cache/runtime-deps.tar"), protocol["runtime_archive_sha256"])
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    assert torch.cuda.is_available()
    assert torch.cuda.get_device_name(0).startswith(protocol["GPU_model"])
    torch.manual_seed(protocol["seed"])
    random.seed(protocol["seed"])
    torch.set_num_threads(2)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = AutoTokenizer.from_pretrained(ROOT, local_files_only=True, trust_remote_code=False,
                                              fix_mistral_regex=False)
    assert digest(ROOT / "tokenizer.json") == protocol["tokenizer_sha256"]
    model = AutoModelForCausalLM.from_pretrained(
        ROOT, local_files_only=True, trust_remote_code=False, device_map={"": 0},
        dtype=torch.bfloat16, attn_implementation="sdpa", low_cpu_mem_usage=True,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                              bnb_4bit_compute_dtype=torch.bfloat16))
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
    model.eval()
    staging_seconds = time.monotonic() - started
    print("MODEL_LOADED " + str(round(staging_seconds, 1)), flush=True)

    def infer(phase):
        model.eval()
        model.config.use_cache = True
        model.gradient_checkpointing_disable()
        records = []
        for idx, row in enumerate(dev, 1):
            prompt = tokenizer.apply_chat_template(row["messages"], tokenize=False,
                                                    add_generation_prompt=True, enable_thinking=False)
            assert prompt.endswith(protocol["expected_prompt_suffix"])
            assert sha(prompt.encode()) == row["prompt_sha256"]
            ids = tokenizer.encode(prompt, add_special_tokens=False)
            assert sha(json.dumps(ids, separators=(",", ":")).encode()) == row["input_ids_sha256"]
            assert len(ids) == row["prompt_tokens"]
            inputs = torch.tensor([ids], device="cuda")
            with torch.no_grad():
                generated = model.generate(inputs, do_sample=False, max_new_tokens=protocol["max_new_tokens"],
                                           use_cache=True, eos_token_id=tokenizer.eos_token_id,
                                           pad_token_id=tokenizer.eos_token_id)[0, len(ids):].tolist()
            stopped = bool(generated and generated[-1] == tokenizer.eos_token_id)
            visible = generated[:-1] if stopped else generated
            records.append({"id": row["id"], "phase": phase,
                            "response": tokenizer.decode(visible, skip_special_tokens=False,
                                                         clean_up_tokenization_spaces=False),
                            "output_tokens": len(generated),
                            "truncated": not stopped and len(generated) >= protocol["max_new_tokens"]})
            if idx % 8 == 0:
                print("INFER " + phase + " " + str(idx) + "/128", flush=True)
        return records

    baseline = infer("baseline")
    output = ROOT / protocol["output_directory"]
    output.mkdir(exist_ok=False)
    (output / "baseline.json").write_text(json.dumps(baseline) + "\n")
    print("BASELINE_SAVED 128", flush=True)
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"],
                                            lora_dropout=0.0, task_type="CAUSAL_LM"))
    params = [p for p in model.parameters() if p.requires_grad]
    assert params and sum(p.numel() for p in params) > 0
    optimizer = torch.optim.AdamW(params, lr=protocol["learning_rate"], weight_decay=0)
    order = list(range(len(train)))
    random.Random(protocol["seed"]).shuffle(order)
    losses = []
    model.train()
    for step, idx in enumerate(order, 1):
        row = train[idx]
        ids = torch.tensor([row["input_ids"]], device="cuda")
        labels = torch.tensor([row["labels"]], device="cuda")
        attention = torch.ones_like(ids)
        optimizer.zero_grad(set_to_none=True)
        loss = model(input_ids=ids, attention_mask=attention, labels=labels).loss
        value = float(loss.detach())
        if not math.isfinite(value):
            raise ValueError("Nonfinite SFT loss")
        loss.backward()
        optimizer.step()
        losses.append(value)
        if step % 32 == 0:
            print("TRAIN " + str(step) + "/512 loss=" + str(round(value, 4)), flush=True)
    model.save_pretrained(output / "adapter")
    adapter = output / "adapter/adapter_model.safetensors"
    assert adapter.is_file() and adapter.stat().st_size > 0
    print("ADAPTER_SAVED 512", flush=True)
    after = infer("post_sft")
    (output / "post_sft.json").write_text(json.dumps(after) + "\n")
    receipt = {"status": "COMPLETE", "scope": "official TRAIN internal development only",
               "model_id": protocol["model_id"], "model_revision": protocol["model_revision"],
               "protocol_sha256": digest(INPUT / "protocol.json"),
               "worker_sha256": digest(INPUT / "worker.py"),
               "train_rows": len(train), "dev_rows": len(dev), "official_TEST_rows": 0,
               "development_gradient_rows": 0, "optimizer_steps": len(losses),
               "first_loss": losses[0], "last_loss": losses[-1],
               "baseline_sha256": digest(output / "baseline.json"),
               "post_sft_sha256": digest(output / "post_sft.json"),
               "adapter_sha256": digest(adapter), "adapter_bytes": adapter.stat().st_size,
               "staging_seconds": round(staging_seconds, 2),
               "wall_seconds": round(time.monotonic() - started, 2),
               "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(),
               "GPU": torch.cuda.get_device_name(0), "GPU_count": 1,
               "truncated_baseline": sum(r["truncated"] for r in baseline),
               "truncated_post_sft": sum(r["truncated"] for r in after)}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("QWEN_GPU_RECEIPT=" + json.dumps(receipt), flush=True)
    for phase, records in (("baseline", baseline), ("post_sft", after)):
        packed = base64.b64encode(gzip.compress(json.dumps(records).encode(), compresslevel=9)).decode()
        print("QWEN_GPU_PREDICTIONS_" + phase.upper() + "=" + packed, flush=True)


if __name__ == "__main__":
    main()
