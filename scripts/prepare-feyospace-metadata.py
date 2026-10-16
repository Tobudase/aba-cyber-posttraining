#!/usr/bin/env python3
"""Pin public Feyospace metadata and tokenizer files without downloading weights."""

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
MODEL = "feyospace/feyospace-v1.1-small"
REVISION = "ab6a8372eceb18c10357e2683ce14808217bf5e9"
FILES = (
    "config.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "chat_template.jinja",
    "processor_config.json",
    "preprocessor_config.json",
)
MAX_BYTES = 20_000_000


def fetch(url):
    # The system curl uses the configured CA trust store on this macOS host.
    result = subprocess.run(
        ["curl", "-fsSL", "--max-time", "60", "--max-filesize", str(MAX_BYTES), url],
        check=True,
        capture_output=True,
    )
    if len(result.stdout) > MAX_BYTES:
        raise RuntimeError("Public metadata download exceeded file bound")
    return result.stdout


def main():
    api_url = f"https://huggingface.co/api/models/{MODEL}/revision/{REVISION}"
    metadata = json.loads(fetch(api_url))
    if (metadata.get("id"), metadata.get("sha")) != (MODEL, REVISION):
        raise RuntimeError("Model identity or revision mismatch")
    if metadata.get("private") or metadata.get("gated"):
        raise RuntimeError("Model is not publicly accessible")
    siblings = {item["rfilename"] for item in metadata.get("siblings", [])}
    if not set(FILES).issubset(siblings):
        raise RuntimeError("A required metadata or tokenizer file is missing")
    dest = ROOT / ".tools/model-tokenizer" / f"feyospace-v1.1-{REVISION[:12]}"
    dest.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in FILES:
        raw = fetch(f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}")
        if name.endswith(".json"):
            json.loads(raw)
        (dest / name).write_bytes(raw)
        manifest[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    config = json.loads((dest / "config.json").read_text())
    tok_config = json.loads((dest / "tokenizer_config.json").read_text())
    if config.get("model_type") != "qwen3_5":
        raise RuntimeError("Unexpected model architecture")
    if "chat_template" not in tok_config and not (dest / "chat_template.jinja").read_text().strip():
        raise RuntimeError("Chat template missing")
    license_file_names = sorted(name for name in siblings if name.upper() in {"LICENSE", "LICENSE.TXT", "COPYING"})
    license_id = (metadata.get("cardData") or {}).get("license")
    lock = {
        "status": "OPEN_WEIGHTS_CANDIDATE_LICENSE_UNVERIFIED",
        "model_id": MODEL,
        "revision": REVISION,
        "architecture": config.get("architectures"),
        "model_type": config["model_type"],
        "parameters": (metadata.get("safetensors") or {}).get("total"),
        "public": True,
        "license_id": license_id,
        "license_files": license_file_names,
        # Repository metadata alone cannot settle derivative-training rights.
        "license_verified_for_posttraining": False,
        "local_metadata_dir": dest.relative_to(ROOT).as_posix(),
        "files": manifest,
        "weights_downloaded_locally": False,
        "training_executed": False,
        "official_cybergym_evaluation_used": False,
        "source": api_url,
    }
    out = ROOT / "configs/feyospace-v1.1.candidate.lock.json"
    out.write_text(json.dumps(lock, indent=2) + "\n")
    print(json.dumps({
        "lock": str(out), "revision": REVISION,
        "metadata_bytes": sum(item["bytes"] for item in manifest.values()),
        "files": len(manifest), "license_verified_for_posttraining": lock["license_verified_for_posttraining"],
        "weights_downloaded_locally": False,
    }, indent=2))


if __name__ == "__main__":
    main()
