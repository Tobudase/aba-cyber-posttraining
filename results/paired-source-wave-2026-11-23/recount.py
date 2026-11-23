"""Recount the public per-response receipts. No network, model, or test data needed."""
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text())


def main():
    screen = load("screening.json")
    rows = screen["rows"]
    calibration = load("calibration.json")["sources"]
    first = load("protocol.json")
    second = load("second-cohort.json")
    assert first["cases"].keys().isdisjoint(second)
    assert set(calibration) == first["cases"].keys() | second.keys()
    assert set(rows) == {k for k, v in calibration.items() if v["calibrated"]}
    assert {"sample_" + k for k in calibration}.isdisjoint(first["reserved"])
    assert set(rows).isdisjoint(screen["prior_screened"])
    assert not screen["official_test_accessed"]
    counted = Counter()
    for k, record in rows.items():
        checks = calibration[k]["checks"]
        assert len(checks) == 2
        for check in checks:
            assert check["ok"] and check["gold"] != check.get("negative", check.get("neg"))
        assert set(record["draws"]) == {str(s) for s in screen["seeds"]}
        for draw in record["draws"].values():
            assert len(draw["raw_visible_sha256"]) == 64
            if draw["final"] == "pass":
                assert draw["ended"] and draw["closed"]
            counted[draw["final"]] += 1
    reverse = load("reverse-directions.json")
    reverse_counts = Counter()
    for record in reverse["sources"].values():
        assert len(record["student"]) == 3 and len(record["teachers"]) == 6
        for seed, attempt in record["teachers"].items():
            reverse_counts[seed.split("-")[0]] += int(attempt["strict"])
        reverse_counts["student"] += sum(int(a["strict"]) for a in record["student"].values())
    packed = load("paired-label-audit.json")
    complete = set()
    for k, row in packed.items():
        assert row["mask_equality"] and row["visible_explanation"]
        c = row["counts"]
        for segment in ("prompt", "format", "answer", "visible"):
            assert len({counts[segment] for counts in c.values()}) == 1
        assert c["D"]["aux"] == c["E"]["aux"]
        assert row["complete_five_arm_row"] == (set(c) == set("ABCDE"))
        if row["complete_five_arm_row"]:
            complete.add(k)
    pairs = [k for k in screen["prior_qualified"] if {k+"-original",k+"-reverse"} <= complete]
    assert all(v["strict"] for v in reverse["one_character_replay"]["6137"].values())
    replay = load("help-replay.json")["rows"]
    for arm, expected in [("a", 0), ("b", 6)]:
        n = sum(v["native"] == "pass" for k in ("1623", "2630") for v in replay[k][arm].values())
        assert n == expected
        assert all(v["native"] == "pass" for v in replay["2828"][arm].values())
    edits = load("student-error-replays.json")
    assert len(edits["new_original_output_name"]) == 2
    assert all(s == "pass" for row in edits["new_original_output_name"].values() for s in row.values())
    assert sum(r["strict"] for row in edits["historical_reversals_command_edit"].values() for r in row.values()) == 6
    assert all(sum(v["final"] == "pass" for v in r["draws"].values()) >= 2 for r in rows.values())
    assert not screen["adjudicated_gaps"]["new_sources_qualified"]
    assert all(r["cleaned"] for r in screen["jobs"].values())
    print(f"New candidate origins {len(calibration)}, new screened origins {len(rows)}, historical screened origins {len(screen['prior_screened'])}")
    print("Student response outcomes", dict(counted))
    print("Historical reverse successes out of nine per model", dict(reverse_counts))
    print("Historical origins with five-arm labels in both directions", sorted(pairs))
    print("New source decisions", screen["adjudicated_gaps"])
    print("All published receipt checks passed.")


if __name__ == "__main__":
    main()
