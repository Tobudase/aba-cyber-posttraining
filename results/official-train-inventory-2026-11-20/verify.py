"""Recount published per-source verdicts. Runs offline using Python's standard library."""
from pathlib import Path
from collections import Counter
import json
import hashlib

def verify(data):
    source=data["source"]
    ids=source["training_source_ids"]
    assert len(ids)==len(set(ids))==source["split_counts"]["train"]
    assert sum(source["split_counts"].values())==source["fresh_relative_to_manifests"]
    assert source["tool_scope"]==source["prior_or_reserved_within_scope"]+source["fresh_relative_to_manifests"]
    assert set(source["split_id_sha256"])==set(source["split_counts"])
    assert hashlib.sha256(("\n".join(sorted(ids))+"\n").encode()).hexdigest()==source["split_id_sha256"]["train"]
    rows=data["student"]
    assert len({r["id"] for r in rows})==len(rows)
    assert {r["id"] for r in rows}==set(data["controls"]["admitted"])
    assert set(data["controls"]["admitted"])|set(data["controls"]["excluded"])==set(ids)
    assert set(data["controls"]["admitted"]).isdisjoint(data["controls"]["excluded"])
    counted=Counter()
    gaps=[]
    structural_exact=0
    for row in rows:
        draws=row["draws"]
        assert [d["seed"] for d in draws]==data["first_seeds"]
        labels=[d["functional"] for d in draws];counted.update(labels)
        structural_exact+=sum(d["upstream_exact"] for d in draws)
        if labels.count("semantic")>=2:gaps.append(row["id"])
    assert dict(counted)==data["first_verdict_counts"]
    assert structural_exact==data["upstream_exact_total"]
    diagnostic=Counter(d["secondary_category"] for r in rows for d in r["draws"])
    assert dict(diagnostic)==data["secondary_category_counts"]
    agreement=sum((d["functional"]=="pass")==bool(d["upstream_exact"]) for r in rows for d in r["draws"])
    assert data["scorer_pass_agreement"]==agreement
    assert sorted(gaps)==sorted(data["first_repeatable_semantic_ids"])
    assert sum(counted.values())==len(rows)*len(data["first_seeds"])
    assert set(data["teacher_draws"])==set(gaps)
    expected_teacher={i for i,ds in data["teacher_draws"].items()
                      if sum(v["behavior"]=="pass" and v["facts_pass"] for v in ds.values())>=2}
    assert expected_teacher==set(data["teacher_both_pass_ids"])==set(data["retest_scores"])
    assert all(set(ds)=={"8407","9407","10407"} for ds in data["teacher_draws"].values())
    assert all(set(ds)=={"11003","11027","11047"} for ds in data["retest_scores"].values())
    expected_confirmed={i for i,ds in data["retest_scores"].items() if list(ds.values()).count("semantic")>=2}
    assert expected_confirmed==set(data["confirmed_ids"])
    assert data["new_model_queries"]==dict(student_first=sum(counted.values()),teacher=3*len(gaps),student_retest=3*len(expected_teacher))
    certified=0
    for i in data["confirmed_ids"]:
        assert sum(v=="semantic" for v in data["retest_scores"][i].values())>=2
        assert sum(d["behavior"]=="pass" and d["facts_pass"] for d in data["teacher_draws"][i].values())>=2
        certified+=1
    types={r["group"] for r in rows if r["id"] in data["confirmed_ids"]}
    assert data["gate_met"]==(certified>=8 and len(types)>=3)
    return dict(screened_new_ids=source["fresh_relative_to_manifests"],training_candidate_ids=len(ids),student_queries=len(rows),generations=sum(counted.values()),verdicts=dict(counted),confirmed=certified,skills=len(types),gate_met=data["gate_met"])

if __name__=="__main__":
    print(json.dumps(verify(json.loads(Path(__file__).with_name("summary.json").read_text())),indent=2))
