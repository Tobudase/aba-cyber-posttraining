"""Recompute both paired evaluation tables from published file-level verdicts."""
from collections import Counter
from itertools import combinations
from pathlib import Path
import json

def recount(directory):
    files = json.loads((directory / 'paired-file-verdicts.json').read_text())
    summary = json.loads((directory / 'summary.json').read_text())
    assert len({row['file_sha256'] for row in files}) == len(files)
    for split in ('holdout', 'retention'):
        cases = [r for r in files if r['split'] == split]
        for metric in ('strict', 'numeric'):
            if metric == 'strict':
                panel = summary['panels'][split]
                outcomes = panel['outcomes']
            else:
                panel = summary['supplement_and_verification']['semantic_panels'][split]
                outcomes = panel
            for arm in ('base', 'answer', 'reason'):
                counts = Counter(r['arms'][arm][metric] for r in cases)
                assert counts == outcomes[arm]
                print(split, metric, arm, f"{counts['pass']}/{len(cases)}")
            for old, new in combinations(('base','answer','reason'), 2):
                differences = [int(r['arms'][new][metric]=='pass') - int(r['arms'][old][metric]=='pass') for r in cases]
                check = panel['paired'][new+'-'+old]
                assert (differences.count(1), differences.count(-1)) == (check['wins'], check['losses'])
if __name__ == '__main__':
    recount(Path(__file__).resolve().parent)
