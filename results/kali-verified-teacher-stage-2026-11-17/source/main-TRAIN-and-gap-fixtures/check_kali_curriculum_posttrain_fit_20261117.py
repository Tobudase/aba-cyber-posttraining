"""CPU-only execution of already-generated TRAIN-fit commands; never selects.

Uses the exact admitted fixture/postcondition worker, with framed transport.
No protected DEV/confirmation/TEST command is executed or added to training.
"""
import argparse
import datetime
import hashlib
import json
import time
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import ROOT, OUT, save, sha
from kali_curriculum_acceptance_20261117 import command
from kali_framed_artifacts_20261117 import parse
from kali_execution_jobs_20261114 import OUT as JOBS, submit, poll, cleanup

STAGE = OUT/'paired-sft'


def prepare(tag, include_native):
    dest = STAGE/'trainfit'/tag
    assert not dest.exists(), 'Never overwrite a fixture attempt'
    dest.mkdir(parents=True)
    rows = {r['id']: r for r in json.loads((OUT/'admission-private.json').read_text())['rows']}
    inputs = json.loads((STAGE/'evaluation-inputs-private.json').read_text())
    fit = {r['id'] for r in inputs if r['panel'] == 'trainfit'}
    gap_ids = {r['id'] for r in rows.values() if r.get('strong_gap')} if include_native else set()
    assert not include_native or len(gap_ids) == 3
    candidates = [r for r in json.loads((OUT/'candidates-r2-private.json').read_text()) if r['id'] in fit | gap_ids]
    supported = {r['id'] for r in candidates}
    assert supported and supported <= {id for id in fit | gap_ids if rows[id]['role'] == 'independent_teacher_A'}
    paths = {'E0': STAGE/'runs/pair/base-predictions.json',
             'answer_only': STAGE/'runs/pair/answer_only-predictions.json',
             'reasoning': STAGE/'runs/pair/reasoning-predictions.json'}
    if include_native:
        paths.update({cid: STAGE/'runs'/cid/'reasoning-predictions.json' for cid in ['A1', 'A2']})
    commands = {}; entries = []; source_hashes = {}
    proto = json.loads((STAGE/'evaluation-protocol.json').read_text())
    for state, path in paths.items():
        data = json.loads(path.read_text()); assert data['status'] == 'COMPLETE'
        source_hashes[state] = sha(path)
        for seed in proto['seeds']:
            for mode in proto['modes']:
                rr = [r for r in data['predictions'] if r['sampling_seed'] == seed and r['mode'] == mode and r['panel'] == 'trainfit']
                assert len(rr) == len(fit) and {r['id'] for r in rr} == fit
                for r in rr:
                    role = state+'__'+mode+'__'+str(seed)
                    entry = {'id': r['id'], 'state': state, 'mode': mode, 'seed': seed, 'role': role}
                    if r['id'] not in supported:
                        entry['status'] = 'UNSUPPORTED_PUBLISHER_REPLAY_NOT_EXECUTED'
                    else:
                        cmd = command(r)
                        entry['status'] = 'READY' if cmd else 'NO_VALID_COMPLETED_OUTPUT'
                        if cmd: commands.setdefault(r['id'], {})[role] = cmd
                    entries.append(entry)
    if include_native:
        confirmation = STAGE/'confirmation'
        frozen = json.loads((confirmation/'selection-freeze-private.json').read_text())
        gap_protocol = json.loads((STAGE/'gap-diagnostic/evaluation-protocol.json').read_text())
        for state in frozen['states']:
            label = state['label']; path = confirmation/'runs'/(label+'-gap-predictions.json')
            data = json.loads(path.read_text())
            assert data['status'] == 'COMPLETE' and len(data['predictions']) == 18
            assert data['inputs_sha256'] == gap_protocol['input_sha256']
            assert data['adapter_sha256'] == state['pointer']['adapter_sha256']
            if data['adapter_sha256']: assert data['reload_audit']['trained_vs_reloaded_probe_identical']
            state_name = 'known_gap_'+label
            source_hashes[state_name] = sha(path)
            expected = {(seed, mode, id) for seed in proto['seeds'] for mode in proto['modes'] for id in gap_ids}
            assert {(r['sampling_seed'],r['mode'],r['id']) for r in data['predictions']} == expected
            for r in data['predictions']:
                assert r['panel'] == 'known_training_gap3'
                role = state_name+'__'+r['mode']+'__'+str(r['sampling_seed'])
                cmd = command(r)
                entries.append({'id':r['id'],'state':state_name,'mode':r['mode'],'seed':r['sampling_seed'],
                                'role':role,'status':'READY' if cmd else 'NO_VALID_COMPLETED_OUTPUT'})
                if cmd: commands.setdefault(r['id'],{})[role]=cmd
    original = ROOT/'scripts/kali_verified_curriculum_worker_20261117.py'
    worker = original.read_text()
    old = "print('VERIFIED_CURRICULUM_ARTIFACT='+base64.b64encode(gzip.compress(json.dumps(artifact).encode())).decode(),flush=True)"
    assert worker.count(old) == 1
    worker = worker.replace(old, "import sys;sys.path.insert(0,'/input');from kali_framed_artifacts_20261117 import emit;emit(artifact,'CURRICULUM_FIT_ARTIFACT')")
    candidate_text = json.dumps(candidates, indent=2)+'\n'
    command_text = json.dumps(commands, indent=2)+'\n'
    src = ROOT/'data/benchkit/kali-independent-teacher-2026-11-17/source-evidence/galleta.c'
    files = {'worker.py': worker, 'kali_framed_artifacts_20261117.py': (ROOT/'scripts/kali_framed_artifacts_20261117.py').read_text(),
             'candidates.json': candidate_text, 'commands.json': command_text, 'galleta.c': src.read_text(), 'galleta.sha256': sha(src)}
    freeze = {'status': 'TRAIN_FIT_ONLY_NOT_SELECTION', 'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'source_predictions_sha256': source_hashes, 'original_oracle_worker_sha256': sha(original),
              'transport_only_worker_sha256': hashlib.sha256(worker.encode()).hexdigest(),
              'candidate_sha256': hashlib.sha256(candidate_text.encode()).hexdigest(),
              'commands_sha256': hashlib.sha256(command_text.encode()).hexdigest(),
              'supported_unique_training_tasks': len(supported), 'publisher_replay_held_unique': len(fit-supported),
              'DEV_or_confirmation_or_TEST_commands': 0, 'GPU': 0, 'training_updates': 0,
              'known_train_gap_unique_tasks':len(gap_ids),
              'states': list(source_hashes), 'entries': entries}
    save(dest/'freeze-private.json', freeze)
    # Capture the actual future CPU batch, rather than substituting mutable
    # current source during final publication. No predicates/commands change.
    (dest/'actually-submitted-worker-private.py').write_text(files['worker.py'])
    (dest/'original-oracle-private.py').write_bytes(original.read_bytes())
    loaded=dest/'loaded-source-private';loaded.mkdir()
    names=['check_kali_curriculum_posttrain_fit_20261117.py','kali_cpu_node_pool_20261118.py',
           'kali_curriculum_acceptance_20261117.py','kali_framed_artifacts_20261117.py']
    for name in names:(loaded/name).write_bytes((ROOT/'scripts'/name).read_bytes())
    save(dest/'source-freeze-private.json',{name:sha(loaded/name) for name in names})
    return dest, freeze, files


def analyze(dest, freeze, artifact):
    assert artifact['source_sha256'] == freeze['candidate_sha256']
    assert artifact['commands_sha256'] == freeze['commands_sha256']
    assert artifact['target_binaries_executed'] == artifact['GPU'] == artifact['model_calls'] == 0
    results = artifact['results']
    expected_ids={r['id'] for r in freeze['entries'] if r['status']!='UNSUPPORTED_PUBLISHER_REPLAY_NOT_EXECUTED'}
    assert expected_ids, 'No supported TRAIN fixtures; cannot certify controls'
    keys=[(r['id'],r['role'],r['variant']) for r in results]
    assert len(keys)==len(set(keys)), 'Duplicate fixture records'
    assert all(r['id'] in expected_ids and r['variant'] in [0,1] for r in results)
    for role in ['reference','negative']:
        actual={(r['id'],r['variant']) for r in results if r['role']==role}
        assert actual=={(id,v) for id in expected_ids for v in [0,1]}, 'Missing mandatory paired '+role+' controls'
    assert all(r['pass'] for r in results if r['role'] == 'reference')
    assert not any(r['pass'] for r in results if r['role'].startswith('negative'))
    assert all(r['status']=='FAIL' and r['pass'] is False for r in results if r['role'].startswith('negative')), 'Negative controls must be explicit failures, not unsupported/UNKNOWN'
    indexed = {}
    for r in results:
        indexed.setdefault((r['id'], r['role']), []).append(r)
    cases = []
    for entry in freeze['entries']:
        case = dict(entry)
        if entry['status'] == 'READY':
            rr = indexed.get((entry['id'], entry['role']), [])
            assert len(rr) == 2 and {r['variant'] for r in rr} == {0, 1}
            case['status'] = 'PASS_BOTH_FIXTURES' if all(r['pass'] for r in rr) else 'UNKNOWN_SCOPED_SYNTAX' if any(r['status'].startswith('UNKNOWN') for r in rr) else 'FAIL_SCOPED_FIXTURE'
        cases.append(case)
    summary = {}
    for state in freeze['states']:
        summary[state] = {}
        for mode in ['thinking', 'nonthinking']:
            rr = [r for r in cases if r['state'] == state and r['mode'] == mode]
            supported = [r for r in rr if r['status'] != 'UNSUPPORTED_PUBLISHER_REPLAY_NOT_EXECUTED']
            summary[state][mode] = {'unique_supported_tasks': len({r['id'] for r in supported}),
                                   'inference_samples': len(supported),
                                   'functional_pass': sum(r['status'] == 'PASS_BOTH_FIXTURES' for r in supported),
                                   'invalid_output': sum(r['status'] == 'NO_VALID_COMPLETED_OUTPUT' for r in supported),
                                   'unknown': sum(r['status'] == 'UNKNOWN_SCOPED_SYNTAX' for r in supported),
                                   'functional_fail': sum(r['status'] == 'FAIL_SCOPED_FIXTURE' for r in supported),
                                   'publisher_replay_unexecuted': len(rr)-len(supported),
                                   'unique_at_least_two_success':sum(sum(r['status']=='PASS_BOTH_FIXTURES' for r in supported if r['id']==id)>=2 for id in {r['id'] for r in supported}),
                                   'per_seed':{str(seed):{'functional_pass':sum(r['status']=='PASS_BOTH_FIXTURES' for r in supported if r['seed']==seed),'n':sum(r['seed']==seed for r in supported)} for seed in [3407,4407,5407]}}
    result = {'status': 'TRAIN_FIT_CPU_VERIFIED_NOT_SELECTION', 'summary': summary,
              'reference_positive_checks': sum(r['role'] == 'reference' for r in results),
              'negative_controls': sum(r['role'].startswith('negative') for r in results),
              'unique_fixture_tasks':len(expected_ids), 'paired_fixture_controls_verified':True,
              'false_passed_negative_controls': 0, 'GPU': 0, 'DEV_or_confirmation_or_TEST_commands': 0,
              'scope': 'Already-seen TRAIN fixture tasks; memorization/fit diagnostic only, not transfer accuracy.',
              'cases': cases}
    save(dest/'analysis-private.json', result)
    print(json.dumps({'status': result['status'], 'summary': summary}))


def main():
    p = argparse.ArgumentParser(); p.add_argument('--tag', choices=['fixed', 'all'], required=True); args = p.parse_args()
    dest, freeze, files = prepare(args.tag, args.tag == 'all')
    name = 'miw113-kali-cur-fit-'+args.tag+'-1117'
    from kali_cpu_node_pool_20261118 import ordinary_cpu_nodes
    print(json.dumps(submit(name, files, {'cpu': '2', 'memory': '4Gi', 'ephemeral-storage': '8Gi'}, runtime=2700,
                            node_names=ordinary_cpu_nodes())), flush=True)
    until = time.monotonic()+4900; previous = None; collected = None
    while time.monotonic() < until:
        try: state = poll(name)
        except Exception as e:
            print('TRANSIENT_POLL '+type(e).__name__, flush=True); time.sleep(30); continue
        state.pop('log_tail', None)
        if state != previous: print(json.dumps(state), flush=True); previous = state
        log = JOBS/name/'worker.log'
        if log.exists():
            artifact = parse(log.read_text(), 'CURRICULUM_FIT_ARTIFACT')
            if artifact is not None:
                collected = artifact; save(dest/'execution-private.json', artifact)
        if state['status'] in ['SUCCEEDED', 'FAILED']:
            if state['status'] == 'SUCCEEDED': assert collected is not None
            cleanup(name)
            assert state['status'] == 'SUCCEEDED', 'Preserve failed fixture attempt; no changes to candidate selection'
            analyze(dest, freeze, collected)
            return
        time.sleep(45)
    raise TimeoutError('Bounded CPU fixture deadline; inspect original job')


if __name__ == '__main__': main()
