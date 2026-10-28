"""Inference-only Qwen base vs saved adapter on frozen unqueried internal DEV."""

import base64
import gzip
import hashlib
import json
import sys
import tarfile
import time
from pathlib import Path


ROOT = Path("/model-cache/qwen3-8b-b968826d9c46")
INPUT = Path("/input")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def unpack(name, expected):
    data = gzip.decompress(base64.b64decode((INPUT / name).read_text(), validate=True))
    assert hashlib.sha256(data).hexdigest() == expected
    return json.loads(data)


def load_deps(expected):
    archive = Path("/deps-cache/runtime-deps.tar")
    assert sha(archive) == expected
    target = Path("/scratch/deps")
    target.mkdir()
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if not member.isfile() or not (target / member.name).resolve().is_relative_to(target.resolve()):
                raise ValueError("Unsafe dependency archive")
        tar.extractall(target, filter="data")
    sys.path.insert(0, str(target))


def main():
    started = time.monotonic()
    p = json.loads((INPUT / "protocol.json").read_text())
    assert p["status"] == "FROZEN_BEFORE_93_MODEL_OUTPUTS"
    assert p["model_id"] == "Qwen/Qwen3-8B"
    assert p["model_revision"] == "b968826d9c46dd6066d109eabc6255188de91218"
    assert p["precision"] == "NF4_QLORA_BF16_COMPUTE"
    assert p["official_TEST_rows"] == p["optimizer_steps"] == 0
    assert sha(INPUT / "worker.py") == p["worker_sha256"]
    dev = unpack("dev-inputs.json.gz.b64", p["dev_inputs_sha256"])
    assert len(dev) == 93 and len({r["id"] for r in dev}) == 93
    assert all(r["official_test"] is False and set(r).isdisjoint({"target", "native_label", "ground_truth_command"})
               for r in dev)
    prior_receipt_path = ROOT / p["prior_output_directory"] / "receipt.json"
    assert sha(prior_receipt_path) == p["prior_GPU_receipt_sha256"]
    prior = json.loads(prior_receipt_path.read_text())
    assert prior["status"] == "COMPLETE" and prior["optimizer_steps"] == 512
    assert prior["protocol_sha256"] == p["prior_protocol_sha256"]
    assert prior["adapter_sha256"] == p["adapter_sha256"]
    adapter_dir = prior_receipt_path.parent / "adapter"
    adapter_file = adapter_dir / "adapter_model.safetensors"
    assert adapter_file.stat().st_size == prior["adapter_bytes"]
    assert sha(adapter_file) == p["adapter_sha256"]
    for name, expected in p["checkpoint_sha256"].items():
        assert sha(ROOT / name) == expected, "Pinned model file mismatch: " + name
    load_deps(p["runtime_archive_sha256"])
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel, prepare_model_for_kbit_training

    assert torch.cuda.is_available()
    assert torch.cuda.get_device_name(0) == "NVIDIA GeForce RTX 3090"
    torch.manual_seed(p["seed"])
    torch.set_num_threads(2)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = AutoTokenizer.from_pretrained(ROOT, local_files_only=True, trust_remote_code=False,
                                              fix_mistral_regex=False)
    assert sha(ROOT / "tokenizer.json") == p["tokenizer_sha256"]
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
        result = []
        for idx, row in enumerate(dev, 1):
            prompt = tokenizer.apply_chat_template(row["messages"], tokenize=False,
                                                    add_generation_prompt=True, enable_thinking=False)
            assert prompt.endswith(p["expected_prompt_suffix"])
            assert hashlib.sha256(prompt.encode()).hexdigest() == row["prompt_sha256"]
            ids = tokenizer.encode(prompt, add_special_tokens=False)
            encoded_sha = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
            assert encoded_sha == row["input_ids_sha256"] and len(ids) == row["prompt_tokens"]
            prompt_tensor = torch.tensor([ids], device="cuda")
            with torch.no_grad():
                generated = model.generate(prompt_tensor, do_sample=False, max_new_tokens=p["max_new_tokens"],
                                           use_cache=True, eos_token_id=tokenizer.eos_token_id,
                                           pad_token_id=tokenizer.eos_token_id)[0, len(ids):].tolist()
            stopped = bool(generated and generated[-1] == tokenizer.eos_token_id)
            visible = generated[:-1] if stopped else generated
            result.append({"id": row["id"], "phase": phase,
                           "response": tokenizer.decode(visible, skip_special_tokens=False,
                                                        clean_up_tokenization_spaces=False),
                           "output_tokens": len(generated),
                           "truncated": not stopped and len(generated) >= p["max_new_tokens"]})
            if idx % 8 == 0 or idx == len(dev):
                print("INFER " + phase + " " + str(idx) + "/93", flush=True)
        return result

    baseline = infer("baseline")
    output = ROOT / p["output_directory"]
    output.mkdir(exist_ok=False)
    (output / "baseline.json").write_text(json.dumps(baseline) + "\n")
    print("BASELINE_SAVED 93", flush=True)
    model = PeftModel.from_pretrained(model, adapter_dir, is_trainable=False, local_files_only=True)
    model.eval()
    print("ADAPTER_LOADED_AND_HASH_VERIFIED", flush=True)
    post = infer("post_sft")
    (output / "post_sft.json").write_text(json.dumps(post) + "\n")
    receipt = {"status": "COMPLETE_INFERENCE_ONLY", "model_id": p["model_id"],
               "model_revision": p["model_revision"], "protocol_sha256": sha(INPUT / "protocol.json"),
               "worker_sha256": sha(INPUT / "worker.py"),
               "prior_GPU_receipt_sha256": p["prior_GPU_receipt_sha256"],
               "adapter_sha256": p["adapter_sha256"],
               "all_unqueried_rows": len(dev), "official_TEST_rows": 0, "optimizer_steps": 0,
               "baseline_sha256": sha(output / "baseline.json"),
               "post_sft_sha256": sha(output / "post_sft.json"),
               "truncated_baseline": sum(r["truncated"] for r in baseline),
               "truncated_post_sft": sum(r["truncated"] for r in post),
               "staging_seconds": round(staging_seconds, 2),
               "wall_seconds": round(time.monotonic() - started, 2),
               "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(),
               "GPU": torch.cuda.get_device_name(0), "GPU_count": 1}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("QWEN_CONFIRM_RECEIPT=" + json.dumps(receipt), flush=True)
    for phase, records in (("baseline", baseline), ("post_sft", post)):
        packed = base64.b64encode(gzip.compress(json.dumps(records).encode(), compresslevel=9)).decode()
        print("QWEN_CONFIRM_PREDICTIONS_" + phase.upper() + "=" + packed, flush=True)


if __name__ == "__main__":
    main()
