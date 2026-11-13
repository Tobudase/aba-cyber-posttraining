#!/usr/bin/env python3
"""One frozen ABA candidate: publisher TRAIN SFT and two internal DEV panels."""

import base64
import concurrent.futures
import gzip
import hashlib
import json
import sys
import tarfile
import time
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def main():
    started = time.monotonic()
    protocol = json.loads(Path("/input/protocol.json").read_text())
    assert protocol["status"] == "FROZEN_REDSAGE_ABA_CANDIDATE_BEFORE_TRAINING"
    assert protocol["official_TEST_rows"] == 0
    assert sha("/input/worker.py") == protocol["worker_sha256"]
    assert sha("/input/kali_append64_sft_recipe.py") == protocol["recipe_sha256"]
    raw = gzip.decompress(Path("/input/payload.json.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == protocol["payload_sha256"]
    payload = json.loads(raw)
    rows = payload["train_rows"]
    dev1 = payload["dev1"]
    dev2 = payload["dev2"]
    anchors = payload["anchors"]
    assert len(rows) == len({r["id"] for r in rows}) == protocol["training_rows"]
    assert len(dev1) == len({r["id"] for r in dev1}) == 64
    assert len(dev2) == len({r["id"] for r in dev2}) == 64
    assert len(anchors) == len({r["id"] for r in anchors}) == 4
    assert not {r["id"] for r in rows} & {r["id"] for r in dev1 + dev2 + anchors}
    assert not {r["id"] for r in dev1} & {r["id"] for r in dev2}
    assert all(r["split"] == "train" and r["training_eligible"] is True and
               r["official_test"] is False for r in rows)
    assert all(set(r) == {"id", "native_messages"} for r in dev1 + dev2)

    model_dir = Path("/scratch/model")
    model_dir.mkdir()

    def stage(item):
        name, expected = item
        assert Path(name).name == name
        src, dst = Path("/cache/model") / name, model_dir / name
        h = hashlib.sha256()
        with src.open("rb") as incoming, dst.open("xb") as outgoing:
            for block in iter(lambda: incoming.read(8 * 1024**2), b""):
                h.update(block)
                outgoing.write(block)
        assert h.hexdigest() == expected
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
    sys.path[:0] = [str(deps), "/input"]

    import torch
    from importlib.metadata import version
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model, set_peft_model_state_dict
    from safetensors.torch import load_file
    from kali_append64_sft_recipe import validate_recipe, train_fixed_sft

    assert {name: version(name) for name in protocol["expected_packages"]} == protocol["expected_packages"]
    assert torch.cuda.is_available()
    gpu = torch.cuda.get_device_name(0)
    assert gpu in protocol["allowed_GPU_models"]
    import os
    assert os.environ.get("CUBLAS_WORKSPACE_CONFIG")==":4096:8"
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)
    torch.set_num_threads(2)
    tok = AutoTokenizer.from_pretrained(model_dir, local_files_only=True,
                                         trust_remote_code=False, fix_mistral_regex=False)
    tok.padding_side = "left"
    tok.pad_token = tok.eos_token
    assert tok.eos_token_id == 151645
    validate_recipe(protocol["optimizer"], rows)
    torch.manual_seed(protocol["initialization_seed"])
    base = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True,
                device_map={"": 0}, torch_dtype=torch.bfloat16, attn_implementation="sdpa")
    base.requires_grad_(False)
    base.enable_input_require_grads()
    torch.manual_seed(protocol["initialization_seed"])
    model = get_peft_model(base, LoraConfig(**protocol["LoRA_config"]))
    init_hash=hashlib.sha256()
    for name,param in sorted(model.named_parameters()):
        if param.requires_grad:
            init_hash.update(name.encode());init_hash.update(param.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes())
    initial_lora_sha256=init_hash.hexdigest()
    model.eval()

    def infer(batch_rows, arm, anchor=False):
        out = []
        for offset in range(0, len(batch_rows), protocol["batch_size"]):
            batch = batch_rows[offset:offset + protocol["batch_size"]]
            prompts = [tok.apply_chat_template(r["native_messages"], tokenize=False,
                       add_generation_prompt=True) for r in batch]
            assert all(p.endswith("<think>") for p in prompts)
            inputs = tok(prompts, padding=True, add_special_tokens=False,
                         return_tensors="pt").to("cuda")
            torch.manual_seed(protocol["inference_seed"])
            with torch.inference_mode():
                generated = model.generate(**inputs, max_new_tokens=protocol["max_new_tokens"],
                    do_sample=False, use_cache=True, pad_token_id=tok.eos_token_id,
                    eos_token_id=tok.eos_token_id, temperature=None, top_p=None, top_k=None)
            for row, ids in zip(batch, generated[:, inputs["input_ids"].shape[1]:].tolist()):
                truncated = tok.eos_token_id not in ids
                effective = ids if truncated else ids[:ids.index(tok.eos_token_id)]
                response = tok.decode(effective, skip_special_tokens=False,
                                      clean_up_tokenization_spaces=False)
                if anchor:
                    assert arm == "base"
                    out.append({"id": row["id"], "arm": arm, "response": response,
                                "expected_l40s_sha256": row["expected_sha256"]["base"],
                                "actual_sha256": hashlib.sha256(response.encode()).hexdigest(),
                                "truncated": truncated, "generated_tokens": len(effective)})
                else:
                    out.append({"id": row["id"], "arm": arm, "response": response,
                                "truncated": truncated, "generated_tokens": len(effective)})
            print("INFER " + arm + " " + str(offset + len(batch)) + "/" + str(len(batch_rows)), flush=True)
        return out

    anchor_audit = infer(anchors, "base", anchor=True)
    assert len(anchor_audit) == 4
    print("MATCHED_SFT733_BASE_ANCHORS=" + base64.b64encode(
        gzip.compress(json.dumps(anchor_audit, ensure_ascii=False).encode())).decode(), flush=True)
    print("BASE_ANCHORS_COMPARED", flush=True)
    base_predictions = infer(dev1 + dev2, "base")
    reference_path=Path('/input/control-base-reference.json')
    if reference_path.exists():
        expected=json.loads(reference_path.read_text())
        assert {r['id']:r['response'] for r in base_predictions}==expected, 'Fresh control baseline mismatch before any training'
    print("ABA_BASE_PREDICTIONS=" + base64.b64encode(gzip.compress(
        json.dumps(base_predictions, ensure_ascii=False).encode())).decode(), flush=True)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.config.use_cache = False

    def progress(step):
        if step["step"] == 1 or step["step"] % 32 == 0:
            print("TRAIN " + json.dumps({k: step[k] for k in (
                "step", "loss", "gradient_norm_before_clip")}), flush=True)

    receipt = train_fixed_sft(model, rows, protocol["optimizer"], "cuda", progress)
    assert receipt["optimizer_steps"] == protocol["training_rows"]
    assert receipt["nonzero_gradient_steps"] == protocol["training_rows"]
    outdir = Path("/cache/kali-8b-append64-study") / protocol["candidate_id"]
    outdir.parent.mkdir(exist_ok=True)
    outdir.mkdir(exist_ok=False)
    model.eval()
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    model.save_pretrained(outdir / "adapter")
    config_path=outdir/"adapter/adapter_config.json"
    adapter_config=json.loads(config_path.read_text());adapter_config.update(base_model_name_or_path=protocol["model_id"],revision=protocol["model_revision"]);config_path.write_text(json.dumps(adapter_config,indent=2)+"\n")
    probe = torch.tensor([rows[0]["input_ids"]], device="cuda")
    with torch.inference_mode():
        before = model(input_ids=probe, use_cache=False).logits[:, -1, :].float().cpu()
    state = load_file(str(outdir / "adapter/adapter_model.safetensors"))
    with torch.no_grad():
        for value in model.parameters():
            if value.requires_grad:
                value.zero_()
    set_peft_model_state_dict(model, state, adapter_name="default")
    with torch.inference_mode():
        after = model(input_ids=probe, use_cache=False).logits[:, -1, :].float().cpu()
    delta = float((before - after).abs().max())
    assert delta <= 1e-4
    receipt.update(status='TRAINING_COMPLETE_BEFORE_DEV_INFERENCE',candidate_id=protocol['candidate_id'],initial_lora_sha256=initial_lora_sha256,adapter_sha256=sha(outdir/'adapter/adapter_model.safetensors'),adapter_config_sha256=sha(outdir/'adapter/adapter_config.json'),protocol_sha256=sha('/input/protocol.json'),adapter_reload_max_logit_delta=delta)
    (outdir/'training-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('STUDY8B_TRAINING_COMPLETE='+json.dumps({k:receipt[k] for k in ['candidate_id','optimizer_steps','nonzero_gradient_steps','initial_lora_sha256','adapter_sha256']}),flush=True)
    predictions = infer(dev1 + dev2, protocol["candidate_id"])
    packed = base64.b64encode(gzip.compress(json.dumps(predictions, ensure_ascii=False).encode())).decode()
    print("ABA_CANDIDATE_PREDICTIONS=" + packed, flush=True)
    receipt.update({"status": "COMPLETE_8B_STUDY_ARM",
                    "candidate_id": protocol["candidate_id"],
                    "run_kind": protocol["run_kind"],
                    "initial_lora_sha256": initial_lora_sha256,
                    "quality_counts":protocol["quality_counts"],
                    "deterministic_algorithms":torch.are_deterministic_algorithms_enabled(),
                    "attention_backend":"math_sdpa",
                    "adapter_sha256": sha(outdir / "adapter/adapter_model.safetensors"),
                    "adapter_reload_max_logit_delta": delta,
                    "GPU": gpu, "GPU_count": 1,
                    "dev_predictions": len(predictions),
                    "base_anchors_compared": len(anchor_audit),
                    "dev_truncations": sum(r["truncated"] for r in predictions),
                    "official_TEST_rows": 0,
                    "worker_sha256": sha("/input/worker.py"),
                    "protocol_sha256": sha("/input/protocol.json"),
                    "wall_seconds": round(time.monotonic() - started, 2),
                    "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated()})
    (outdir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    public_receipt = {k: receipt[k] for k in (
        "status", "candidate_id", "run_kind", "initial_lora_sha256", "quality_counts", "deterministic_algorithms", "attention_backend", "adapter_config_sha256", "adapter_sha256", "adapter_reload_max_logit_delta", "GPU", "GPU_count",
        "dev_predictions", "dev_truncations", "base_anchors_compared", "official_TEST_rows",
        "worker_sha256", "protocol_sha256", "wall_seconds", "peak_cuda_allocated_bytes",
                    "optimizer_steps", "nonzero_gradient_steps", "changed_tensors",
                    "supervised_token_presentations")}
    print("ABA_CANDIDATE_RECEIPT=" + json.dumps(public_receipt), flush=True)


if __name__ == "__main__":
    main()
