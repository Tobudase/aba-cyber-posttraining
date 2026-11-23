"""Export numeric evidence from private run receipts. Never export trajectory text."""
import argparse
import hashlib
import json
from pathlib import Path

from tokenizers import Tokenizer


def read(path):
    return json.loads(path.read_text())


def digest(content):
    return hashlib.sha256(content).hexdigest()


def get_trace(draw):
    if not draw['closed']:
        return None
    text = draw['trace'].strip()
    # The worker split on the closing marker and retained the opening marker.
    if not text.startswith('<think>'):
        return None
    return text[len('<think>'):].strip()


def audit(work):
    local = work / 'readonly-teacher-match'
    jobs = work / 'data/benchkit/kali-execution-2026-11-14'
    original = read(local / 'single-private.json')
    aligned = read(local / 'aligned-private.json')
    grades = read(local / 'single-aligned-results.json')
    plan = json.loads(read(jobs / 'miw113-json-triad-flex22/objects.json')[0]['data']['task.json'])
    assert original['dir'].endswith(plan['run_hash'])
    tokenizer_file = work / '.tools/model-tokenizer/qwen3-8b-b968826d9c46/tokenizer.json'
    tokenizer_digest = digest(tokenizer_file.read_bytes())
    assert tokenizer_digest == 'aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4'
    tokenizer = Tokenizer.from_file(str(tokenizer_file))

    def encode(text):
        return tokenizer.encode(text, add_special_tokens=False).ids

    teachers = {}
    targets = {}
    for arm, name in [('B', 'qwen'), ('C', 'deepseek')]:
        receipt = read(work / 'access-followup-1122/private' / name / '22103.json')
        response = receipt['response']
        message = response['choices'][0]['message']
        raw = message.get('reasoning') or message['reasoning_content']
        assert raw == plan['traces'][arm]
        assert json.loads(message['content'])['command'] == plan['command']
        review = read(local / 'review.json')[name+'-22103']
        assert review['admitted'] and review['trace_sha256'] == digest(raw.encode())
        assert all(raw not in r['prompt'] for r in plan['rows']) and raw not in plan['system']
        targets[arm] = encode(raw.strip())
        teachers[arm] = dict(model=response['model'], tokens=len(targets[arm]),
                             raw_sha256=digest(raw.encode()),
                             leading_whitespace=len(raw)-len(raw.lstrip()),
                             trailing_whitespace=len(raw)-len(raw.rstrip()),
                             normalized_sha256=digest(raw.strip().encode()))
    assert targets['B'] != targets['C']
    arms = dict(original['arms'], A=aligned['arms']['A'])
    assert len({v['init'] for v in arms.values()}) == 1
    groups = {'base': original['base'], 'base_recheck': aligned['base']}
    for arm, record in arms.items():
        assert record['checks'] == grades['checkpoints'][arm]['hashes']
        for step, cases in record['eval'].items():
            groups[arm+step] = cases
    rows = {}
    for checkpoint, draws in groups.items():
        rows[checkpoint] = {}
        for case, draw in draws.items():
            body = get_trace(draw)
            ids = encode(body) if body is not None else []
            hashed = digest(body.encode()) if body is not None else None
            comparisons = {}
            for arm, ref in targets.items():
                prefix = next((i for i, (a, b) in enumerate(zip(ids, ref)) if a != b),
                              min(len(ids), len(ref)))
                exact = body is not None and hashed == teachers[arm]['normalized_sha256']
                assert exact == (ids == ref)
                comparisons[arm] = dict(exact=exact, common_prefix_tokens=prefix)
            grade = grades['details'][checkpoint+'-'+case]
            assert grade['ended'] == draw['ended'] and grade['tokens'] == draw['tokens']
            rows[checkpoint][case] = dict(ended=draw['ended'], closed=draw['closed'],
                                          trace_tokens=len(ids) if body is not None else None,
                                          trace_sha256=hashed, comparison=comparisons,
                                          spelling_mentions={flag: body.count(flag) for flag in
                                                             ('--no-not_empty', '--no-not-empty')}
                                          if body is not None else None,
                                          native_behavior=grade['behavior'], strict=grade['strict'])
    return dict(source='sample_6137', training_seed=grades['seed'], decoding_seed=grades['decode_seed'],
                tokenizer_sha256=tokenizer_digest, teachers=teachers, rows=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('private_workspace', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.private_workspace), indent=2)+'\n')
