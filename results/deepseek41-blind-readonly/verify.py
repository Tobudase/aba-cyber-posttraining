import json
from pathlib import Path

p = Path(__file__).resolve().parent
doc = json.loads((p / 'teacher-summary.json').read_text())
for arm, expected in [('teacher', (3, 4)), ('long', (2, 0))]:
    draw_sets = doc['arms'][arm]
    assert len(draw_sets) == 4
    draws = [d for responses in draw_sets.values() for d in responses]
    assert all({d['seed'] for d in responses} == {8407, 9407, 10407} for responses in draw_sets.values())
    assert all(d['fixtures'] == [True, True] and d['rc'] == [0, 0] for d in draws if d['behavior'])
    actual = sum(d['joint'] for d in draws), sum(not d['ended'] for d in draws)
    assert actual == expected and not any(d['raw_fit_eligible'] for d in draws)
    print(arm, 'joint passes, truncations:', actual)
assert len(doc['token_labels']) == 5
assert all(x['answer']['answer'] == x['trace']['answer'] and x['trace']['trace'] > 0 for x in doc['token_labels'].values())
assert doc['official_test_calls'] == 0
