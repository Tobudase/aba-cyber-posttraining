#!/usr/bin/env python3
"""Check chart source consistency and publication integrity without inference."""
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "results/kali-results-figures-2026-10-26"


def read(path):
    return json.loads(path.read_text())


def main():
    manifest = read(DIRECTORY / "publication-manifest.json")
    for name, expected in manifest["file_sha256"].items():
        path = ROOT / name
        assert path.resolve().is_relative_to(ROOT) and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
    data = read(DIRECTORY / "plotted-data.json")
    for name, expected in data["source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    history = read(ROOT / "results/kali-seed43-replication-2026-10-25/summary.json")
    assert data["history"] == history["scores"]
    for source, field in [("same-text-resegmentation.json", "segmentation_TRAIN_sets"),
                          ("matched-control.json", "loss_weight_TRAIN_sets")]:
        original = read(ROOT / "results/kali-prefix-control-2026-10-26" / source)
        assert data[field] == original["sets"]
        assert original["training_sanity_gate_passed"] is False
    assert data["full_segmentation_gate_passed"] is False
    assert data["formal_default"] == "original_base" and data["new_model_calls_or_training_steps"] == 0
    for stem in ["01-development-and-transfer", "02-train-segmentation-control", "03-critical-prefix-loss-control"]:
        png = (DIRECTORY / (stem + ".png")).read_bytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", png[16:24])
        assert width >= 1800 and height >= 900
        assert ET.parse(DIRECTORY / (stem + ".svg")).getroot().tag.endswith("svg")
    print(json.dumps({"status": "PASS_RESULT_FIGURES", "figures": 3,
                      "source_files": len(data["source_sha256"]),
                      "files_verified": len(manifest["file_sha256"]),
                      "new_model_calls_or_training_steps": 0,
                      "private_inference_reproduced": False}))


if __name__ == "__main__":
    main()
