"""Prepare matched-size replay arms without looking at fresh confirmation data."""
import collections
import gzip
import hashlib
import json
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'data/benchkit/kali-counterfactual-v9-2026-11-16'
contracts = ROOT / 'data/benchkit/kali-old-intent-contracts-2026-11-16'
dest = ROOT / 'data/benchkit/kali-retention-v13-2026-11-16'
dest.mkdir(exist_ok=True)
assert not (dest / 'launch-freeze.json').exists(), 'Never mutate a launched study'
audit = json.loads((contracts / 'encoding-audit.json').read_text())
assert audit['status'] == 'ENCODING_AND_SOURCE_PARSER_VERIFIED'
assert hashlib.sha256((contracts / 'encoded-private.json').read_bytes()).hexdigest() == audit['encoded_sha256']
data = json.loads(gzip.decompress((source / 'gpu-inputs.json.gz').read_bytes()))
targeted = json.loads((contracts / 'encoded-private.json').read_text())
control = []
for tool, count in [('setterm', 12), ('hashid', 6), ('appid_detector_builder.sh', 6)]:
    rows = [r for r in data['train_trusted'] if r['tool'] == tool]
    random.Random(431).shuffle(rows)
    control.extend(rows[:count])
assert len(control) == len(targeted) == 24
assert len({r['id'] for r in control}) == len({r['id'] for r in targeted}) == 24
eval_ids = {r['id'] for rows in data['panels'].values() for r in rows}
assert not eval_ids & {r['id'] for r in control + targeted}
assert all(r['split'] == 'train' and r['training_eligible'] and not r['official_test'] for r in control + targeted)
data['auxiliary_replay'] = {'R': control, 'RK': targeted}
refs = json.loads((source / 'references-private.json').read_text())
trusted_messages = {r['id']: r for r in data['trusted_messages']}
data['auxiliary_eval_messages'] = [trusted_messages[r['id']] for r in control] + [
    {'id': r['id'], 'native_messages': r['native_messages']} for r in targeted]
for r in targeted:
    refs[r['id']] = r['native_label']
(dest / 'references-private.json').write_text(json.dumps(refs, indent=2) + '\n')
for name in ['fixtures.json', 'historical-correct-retention-protocol.json']:
    shutil.copyfile(source / name, dest / name)
raw = gzip.compress(json.dumps(data, separators=(',', ':')).encode(), mtime=0)
(dest / 'gpu-inputs.json.gz').write_bytes(raw)
protocol = {
    'status': 'PREPARED_NOT_TRAINED',
    'hypothesis': 'Source-parser-verified missing old intents recover old strict correctness more effectively than additional replay of existing trusted intents.',
    'source': 'The direct-CE endpoint of v11, fixed before reading its comparison results; no validation-based source selection.',
    'old_KL_anchor': 'Original R120, unchanged from v11.',
    'arms': {'R': '24 existing trusted TRAIN rows, proportionally sampled 12/6/6 across existing tools',
             'RK': '24 source-parser-verified missing-intent TRAIN rows, 12 smb2-quota and 12 sprayhound'},
    'shared': {'optimizer': 'fresh AdamW', 'learning_rate': 5e-6, 'updates_each': 96,
               'new_TRAIN_rows_per_update': 4, 'trusted_replay_rows_per_update': 4,
               'generic_old_KL_rows_per_update': 2, 'auxiliary_replay_rows_per_update': 4,
               'auxiliary_weight': 0.5, 'auxiliary_loss': 'example-mean command CE + 0.1 full-completion CE',
               'auxiliary_exposures_each': 384, 'seed': 42},
    'data_sha256': hashlib.sha256(raw).hexdigest(),
    'encoded_contracts_sha256': audit['encoded_sha256'],
    'evaluation': 'Same frozen native scoring, legacy64/newDEV32/shiftedDEV64 functional checks, fullTRAIN384, and paired old64 retention. Auxiliary48 is training-fit diagnosis only.',
    'limitations': ['One continuation seed; replay content and its tool mix change together.',
                   'The extra contracts were authored after inspecting development failures; they cannot support an unseen-test claim.',
                   'Source-parser checks do not certify runtime/network behavior; no sprayhound command is executed.',
                   'No fresh confirmation query, official TEST query, or model promotion.'],
    'budget_matching': 'Same optimizer steps and row exposures, not exact tokens or wall time. Commands differ in length; each auxiliary loss is normalized per example.',
    'auxiliary_token_exposures': {k: {'full_completion': 16*sum(sum(t!=-100 for t in r['labels']) for r in rows), 'command': 16*sum(sum(t!=-100 for t in r['kl_labels']) for r in rows)} for k, rows in data['auxiliary_replay'].items()},
    'maximum_optimizer_steps_total': 192,
    'maximum_model_responses': 2200,
    'maximum_GPU_seconds': 10800,
}
(dest / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
print(json.dumps({'status': protocol['status'], 'auxiliary_rows': {k: len(v) for k, v in data['auxiliary_replay'].items()}, 'payload_sha256': protocol['data_sha256']}))
