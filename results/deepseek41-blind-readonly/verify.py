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

student = json.loads((p / 'student-summary.json').read_text())
blind = student['arms']['studentblind']
manual = student['arms']['studentmanual']
assert student['revision'] == doc['revision']
pairs = {'both': 0, 'manual_only': 0, 'blind_only': 0, 'neither': 0}
for i in blind:
    b = {d['seed']: d for d in blind[i]}
    m = {d['seed']: d for d in manual[i]}
    assert set(b) == set(m) == {11003, 11027, 11047}
    for s in b:
        for d in (b[s], m[s]):
            assert d['parsed'] and d['ended']
            if d['joint']:
                assert d['behavior'] and d['fixtures'] == [True, True] and d['rc'] == [0, 0]
        key = ('both' if m[s]['joint'] else 'blind_only') if b[s]['joint'] else ('manual_only' if m[s]['joint'] else 'neither')
        pairs[key] += 1
assert {k:v for k,v in pairs.items() if v} == student['paired_student_joint_counts']
assert pairs == {'both': 1, 'manual_only': 7, 'blind_only': 0, 'neither': 4}
assert all(d['repeated_parameter_error'] for d in blind['sample_2632'])
assert all(rc == 1 for rc in student['fresh_blind_parameter_probes'].values())
print('student paired outcomes:', pairs)
