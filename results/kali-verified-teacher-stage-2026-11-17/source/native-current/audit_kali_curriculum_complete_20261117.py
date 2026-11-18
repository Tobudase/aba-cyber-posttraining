"""Recompute the full study from real receipts; incomplete stages fail closed.

Writes private audit and aggregate results only after all execution evidence
exists. Never trains, selects from confirmation, or changes a frozen scorer.
"""
import argparse
import contextlib
import datetime
import hashlib
import io
import json
import math
from pathlib import Path

from prepare_kali_verified_curriculum_20261117 import ROOT, OUT, save, sha
from score_kali_curriculum_sft_20261117 import score_predictions, grade

STAGE = OUT / 'paired-sft'


def read(p):
    return json.loads(Path(p).read_text())


def validate_training(data, arm, receipt, trace, expected_sha, learning_rate):
    p = data['protocol']
    encoded = {r['id']: r for r in data['encoded'][arm]}
    expected_batches = [order[off:off+p['effective_batch']]
                        for order in data['epoch_orders']
                        for off in range(0, len(order), p['effective_batch'])]
    assert receipt['data_sha256'] == expected_sha
    assert receipt['updates'] == len(trace) == len(expected_batches) == p['optimizer_updates_per_arm']
    assert receipt['learning_rate'] == learning_rate
    assert receipt['epochs'] == p['epochs'] and receipt['effective_batch'] == p['effective_batch']
    assert receipt['model_revision'] == data['model_protocol']['model_revision']
    ordered = data['encoded'][arm]
    for i, (step, batch) in enumerate(zip(trace, expected_batches)):
        assert step['step'] == i + 1
        assert step['epoch'] == i // math.ceil(len(ordered) / p['effective_batch']) + 1
        assert step['ids'] == [ordered[k]['id'] for k in batch], 'Sample order/exposure differs'
        assert step['target_tokens'] == sum(encoded[id]['target_tokens'] for id in step['ids'])
        assert step['command_tokens'] == sum(sum(encoded[id]['command_mask'][1:]) for id in step['ids'])
        assert math.isfinite(step['gradient_norm']) and step['gradient_norm'] > 0
        assert all(math.isfinite(step[k]) and step[k] >= 0 for k in ['loss', 'command_loss_monitor'])
    assert receipt['training_target_tokens'] == sum(t['target_tokens'] for t in trace)
    assert len(receipt['adapter_sha256']) == len(receipt['initial_adapter_sha256']) == 64
    assert receipt['seconds'] > 0
    return {'updates': len(trace), 'nonzero_gradient_steps': len(trace),
            'target_tokens': receipt['training_target_tokens'], 'training_seconds': receipt['seconds'],
            'learning_rate': learning_rate,
            'first_epoch_mean_loss': sum(t['loss'] for t in trace if t['epoch'] == 1) / math.ceil(len(ordered)/p['effective_batch']),
            'last_epoch_mean_loss': sum(t['loss'] for t in trace if t['epoch'] == p['epochs']) / math.ceil(len(ordered)/p['effective_batch']),
            'first_epoch_command_loss': sum(t['command_loss_monitor'] for t in trace if t['epoch'] == 1) / math.ceil(len(ordered)/p['effective_batch']),
            'last_epoch_command_loss': sum(t['command_loss_monitor'] for t in trace if t['epoch'] == p['epochs']) / math.ceil(len(ordered)/p['effective_batch'])}


def validate_predictions(data, inputs, proto, adapter_sha):
    assert data['status'] == 'COMPLETE'
    assert data['adapter_sha256'] == adapter_sha
    assert data['inputs_sha256'] == proto['input_sha256']
    assert data['no_evaluation_gold_loaded'] is True
    panels = {r['id']: r['panel'] for r in inputs}
    expected = {(seed, mode, id) for seed in proto['seeds'] for mode in proto['modes'] for id in panels}
    rows = data['predictions']
    assert len(rows) == len(expected)
    assert {(r['sampling_seed'], r['mode'], r['id']) for r in rows} == expected
    for r in rows:
        assert r['panel'] == panels[r['id']]
        assert r['finish_reason'] in ['stop', 'length']
        assert 0 <= r['generated_tokens'] <= proto['max_new_tokens']
        if r['finish_reason'] == 'length':
            assert r['generated_tokens'] == proto['max_new_tokens']
    if adapter_sha:
        assert data['reload_audit']['trained_vs_reloaded_probe_identical'] is True
    return {'responses': len(rows), 'seconds': data['seconds'],
            'truncated': sum(r['finish_reason'] == 'length' for r in rows),
            'generated_tokens': sum(r['generated_tokens'] for r in rows)}


def paired_changes(new, base):
    """Private paired-case index, no raw command/trace exported by this function."""
    b = {(r['sampling_seed'], r['mode'], r['id']): r for r in base['details']}
    rows = []
    for r in new['details']:
        old = b[(r['sampling_seed'], r['mode'], r['id'])]
        if bool(r['correct']) != bool(old['correct']) or r['truncated'] != old['truncated'] or r['valid'] != old['valid']:
            rows.append({'id': r['id'], 'seed': r['sampling_seed'], 'mode': r['mode'], 'panel': r['panel'],
                         'change': 'win' if r['correct'] and not old['correct'] else 'loss' if old['correct'] and not r['correct'] else 'reliability_only',
                         'before_status': old['equivalence_status'], 'after_status': r['equivalence_status'],
                         'before_truncated': old['truncated'], 'after_truncated': r['truncated'],
                         'before_valid': old['valid'], 'after_valid': r['valid']})
    aggregate = {}
    for mode in ['thinking', 'nonthinking']:
        aggregate[mode] = {}
        for panel in ['development24', 'old64']:
            rr = [r for r in rows if r['mode'] == mode and r['panel'] == panel]
            aggregate[mode][panel] = {k: sum(r['change'] == k for r in rr) for k in ['win', 'loss', 'reliability_only']}
    return {'aggregate': aggregate, 'private_cases': rows}


def audit_confirmation_files(folder, stage, selection):
    """Validate every actual endpoint and separate TRAIN diagnostic artifact."""
    folder, stage = Path(folder), Path(stage)
    freeze = read(folder/'selection-freeze-private.json')
    launch = read(folder/'launch-freeze-private.json')
    execution = read(folder/'runs/execution-receipt.json')
    assert execution['status'] == 'COMPLETE' and execution['training_updates'] == 0
    if launch.get('submitted_source_snapshot_required'):assert (folder/'submitted-source-freeze-private.json').is_file()
    if (folder/'submitted-source-freeze-private.json').exists():
        frozen=read(folder/'submitted-source-freeze-private.json')
        for name,digest in frozen.items():assert sha(folder/'submitted-source-private'/name)==digest
        assert frozen['kali_curriculum_confirmation_with_gap_worker_20261117.py']==execution['worker_sha256']
        assert execution['all_endpoints_exact_reload_preflight_passed_before_queries'] and execution['confirmation_inference_started']
        states=[s for s in freeze['states'] if s['pointer']['adapter_sha256']]
        assert set(execution['TRAIN_receipt_preflight'])=={s['label'] for s in states}
        for state in states:
            check=execution['TRAIN_receipt_preflight'][state['label']]
            assert check['exact_original_TRAIN_logit_probe_identical'] and check['adapter_sha256']==state['pointer']['adapter_sha256']
    assert execution['official_TEST_queries'] == 0 and execution['confirmation_unique_tasks'] == 24
    assert execution['selection_sha256'] == freeze['selection_sha256'] == launch['config']['selection_sha256']
    assert execution['worker_sha256'] == launch['config']['worker_sha256']
    assert execution['bundle_sha256'] == launch['config']['bundle_sha256']
    for filename, key in [('evaluation-inputs-private.json','input_sha256'),
                          ('evaluation-protocol.json','protocol_sha256'),
                          ('references-private.json','reference_sha256'),
                          ('groups-private.json','groups_sha256')]:
        assert sha(folder/filename) == freeze[key], 'Confirmation input/protocol changed'
    inputs = read(folder/'evaluation-inputs-private.json')
    protocol = read(folder/'evaluation-protocol.json')
    assert len(inputs) == len({r['id'] for r in inputs}) == 24
    gap = stage/'gap-diagnostic'
    gap_freeze = read(gap/'protocol-before-results-private.json')
    assert gap_freeze['not_generalization'] and gap_freeze['does_not_change_selection_or_confirmation']
    assert sha(gap/'evaluation-inputs-private.json') == gap_freeze['inputs_sha256']
    assert sha(gap/'evaluation-protocol.json') == gap_freeze['protocol_sha256']
    assert sha(gap/'protocol-before-results-private.json') == launch['config']['known_TRAIN_gap_protocol_sha256']
    expected_adapters = {'E0': None, 'native_selected': selection['native_selected_pointer']['adapter_sha256']}
    for arm in ['answer_only', 'reasoning']:
        expected_adapters['fixed_'+arm] = read(stage/'runs/pair'/arm/'receipt.json')['adapter_sha256']
    states = {s['label']:s for s in freeze['states']}
    assert len(states) == len(freeze['states']) and set(states) == set(execution['states'])
    for label, adapter in expected_adapters.items():
        resolved = freeze['aliases'].get(label,label)
        assert resolved in states and states[resolved]['pointer']['adapter_sha256'] == adapter
    measured = {}
    for label, state in states.items():
        adapter = state['pointer']['adapter_sha256']
        output = read(folder/'runs'/(label+'-predictions.json'))
        measured[label] = {'confirmation':validate_predictions(output, inputs, protocol, adapter)}
        known = read(folder/'runs'/(label+'-gap-predictions.json'))
        measured[label]['known_TRAIN'] = validate_predictions(known, read(gap/'evaluation-inputs-private.json'),
                                                            read(gap/'evaluation-protocol.json'), adapter)
        assert execution['states'][label]['responses'] == measured[label]['confirmation']['responses'] == 144
        assert execution['states'][label]['known_TRAIN_gap_responses'] == measured[label]['known_TRAIN']['responses'] == 18
        assert execution['states'][label]['adapter_sha256'] == adapter
    return measured


def validate_native_update_provenance(controller, selection, prior_state=None):
    provenance=controller['native_training_provenance']
    assert set(provenance)=={'A1','A2'}
    assert selection['new_optimizer_steps_total']==64
    mode=controller.get('native_execution_mode')
    if mode=='EXPLICIT_EXISTING_A1_A2_REVALIDATION':
        assert prior_state is not None and set(prior_state)=={'A1','A2'}
        assert selection['execution_mode']==mode and selection['new_optimizer_steps_current_native_run']==0
        assert selection['new_optimizer_steps_prior_native_dispatch']==64
        assert selection['native_recipes']=={'A1':5e-6,'A2':2e-5}
        for cid in ['A1','A2']:
            assert provenance[cid]==prior_state[cid]['training_provenance']
            p=provenance[cid]
            assert p['new_optimizer_steps_this_run']==0 and p['reused_candidate_training']
            assert p['new_optimizer_steps_in_study']==32 and p['original_run_protocol_invalid']
            assert p['original_A1_framework_worker_failed'] is False
        return {'A1':0,'A2':0}
    if mode=='EXPLICIT_EXISTING_A1_PLUS_FRESH_A2':
        assert prior_state is not None
        assert provenance['A1']==prior_state['training_provenance']
        assert provenance['A1']['new_optimizer_steps_this_run']==0 and provenance['A1']['reused_candidate_training']
        assert provenance['A1']['new_optimizer_steps_in_study']==32 and provenance['A1']['original_Worker_stays_failed']
        assert selection['execution_mode']==mode and selection['new_optimizer_steps_current_native_run']==32
        assert selection['new_optimizer_steps_prior_native_dispatch']==32
        assert selection['native_recipes']=={'A1':5e-6,'A2':2e-5}
        assert provenance['A2']['new_optimizer_steps_this_run']==32 and not provenance['A2']['reused_candidate_training']
        return {'A1':0,'A2':32}
    assert mode is None, 'Unknown recovery mode must not bypass fresh-training checks'
    assert all(p['new_optimizer_steps_this_run']==32 and not p['reused_candidate_training'] for p in provenance.values())
    return {'A1':32,'A2':32}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixed-only', action='store_true', help='Audit completed pair without claiming native/confirmation completion')
    args = parser.parse_args()
    required = [STAGE/'runs/pair/execution-receipt.json', STAGE/'runs/pair/score-private.json']
    if not args.fixed_only:
        required += [STAGE/'native-selection-private.json', STAGE/'native-controller/host-private.json',
                     STAGE/'confirmation/analysis-private.json', STAGE/'confirmation/runs/execution-receipt.json']
    missing = [str(p.relative_to(STAGE)) for p in required if not p.exists()]
    if missing:
        print(json.dumps({'status': 'INCOMPLETE_NO_FINAL_RESULT', 'missing_evidence': missing}))
        return 2
    payload = STAGE/'paired-training-private.json'; data = read(payload); proto = read(STAGE/'evaluation-protocol.json')
    assert sha(payload) == read(STAGE/'encoding-audit.json')['payload_sha256']
    assert sha(OUT/'admission-private.json') == data['protocol']['admission_sha256']
    assert sha(STAGE/'evaluation-inputs-private.json') == proto['input_sha256']
    admission = read(OUT/'admission-private.json')
    for r in admission['rows']:
        if r['role'] == 'independent_teacher_A':
            assert not r['reasoning_edited'] and not r['expert_human_gold']
            teacher = Path(r['teacher_file'])
            if not teacher.is_absolute():
                teacher = OUT / teacher
            assert sha(teacher) == r['teacher_file_sha256']
            raw = read(teacher)
            assert raw['condition'] == 'U' and raw['reference_command_provided'] is False
            assert r['reasoning'] == (raw['message'].get('reasoning') or raw['message'].get('reasoning_content'))
    assert [r['id'] for r in data['encoded']['answer_only']] == [r['id'] for r in data['encoded']['reasoning']]
    assert [r['command_sha256'] for r in data['encoded']['answer_only']] == [r['command_sha256'] for r in data['encoded']['reasoning']]
    inputs = read(STAGE/'evaluation-inputs-private.json')
    pair = STAGE/'runs/pair'; execution = read(pair/'execution-receipt.json'); launch = read(pair/'launch-freeze-private.json')
    from audit_kali_curriculum_baseline_resume_20261117 import main as audit_baseline_resume
    with contextlib.redirect_stdout(io.StringIO()):
        baseline_resume=audit_baseline_resume()
    assert execution['status'] == 'COMPLETE'
    assert execution['bundle_sha256'] == launch['config']['bundle_sha256']
    assert execution['worker_sha256'] == launch['config']['worker_sha256']
    assert execution['official_TEST_queries'] == execution['confirmation_queries'] == 0
    assert execution['fresh_original_for_each_arm'] is True
    measurements = {}; scores = {}; initialization = []; hashes = {}
    def audit_state(cid, directory, arm=None, lr=None):
        pred_path = directory/('base-predictions.json' if arm is None else arm+'-predictions.json')
        if arm:
            receipt = read(directory/arm/'receipt.json'); trace = read(directory/arm/'trace.json')
            expected = sha(payload) if directory == pair else hashlib.sha256((json.dumps(dict(data, protocol=dict(data['protocol'], learning_rate=lr)))+'\n').encode()).hexdigest()
            training = validate_training(data, arm, receipt, trace, expected, lr)
            initialization.append(receipt['initial_adapter_sha256']); adapter = receipt['adapter_sha256']
        else:
            training = {'updates': 0}; adapter = None
        predictions = read(pred_path)
        measurements[cid] = {'training': training, 'evaluation': validate_predictions(predictions, inputs, proto, adapter)}
        scores[cid] = score_predictions(pred_path)
        hashes[str(pred_path.relative_to(STAGE))] = sha(pred_path)
    audit_state('E0', pair)
    for arm in ['answer_only', 'reasoning']:
        audit_state(arm, pair, arm, data['protocol']['learning_rate'])
    canonical = read(pair/'score-private.json')
    for cid in ['E0', 'answer_only', 'reasoning']:
        assert scores[cid] == canonical['details'][cid], 'Recomputed fixed metrics differ'
        g = grade(scores[cid], scores['E0'])
        if cid == 'E0':
            g.update(score=0., eligible=True)
        assert g == canonical['results'][cid]
    changes = {cid+'_minus_E0': paired_changes(scores[cid], scores['E0']) for cid in ['answer_only', 'reasoning']}
    changes['reasoning_minus_answer_only'] = paired_changes(scores['reasoning'], scores['answer_only'])
    native = None; confirmation = None; confirmation_measurements = None
    if not args.fixed_only:
        controller = read(STAGE/'native-controller/host-private.json'); selection = read(STAGE/'native-selection-private.json')
        journal = read(STAGE/'native-controller/journal-private.json')
        assert controller['native_completed'] and controller['status'] == 'COMPLETE_VERIFIED_NATIVE_TEACHER_ABA'
        assert not controller.get('cleanup_pending') and not controller.get('cleanup_errors')
        runtime_freeze=read(STAGE/'native-controller/native-task-freeze-private.json')
        executed_driver=STAGE/'native-controller/actually-loaded-host-driver-private.py'
        if not executed_driver.exists():executed_driver=ROOT/'scripts/run_kali_curriculum_native_20261117.py'
        driver_name=controller.get('driver_source_name','run_kali_curriculum_native_20261117.py')
        assert driver_name in ['run_kali_curriculum_native_20261117.py','run_kali_curriculum_recovery_20261117.py','run_kali_curriculum_protocol_completion_20261117.py']
        assert sha(executed_driver)==controller['driver_sha256']==runtime_freeze['runtime_source_sha256'][driver_name]
        executed_admission=STAGE/'native-controller/actually-loaded-admission-helper-private.py'
        if not executed_admission.exists():executed_admission=ROOT/'scripts/kali_curriculum_admission_retry_20261117.py'
        assert sha(executed_admission)==runtime_freeze['runtime_source_sha256']['kali_curriculum_admission_retry_20261117.py']
        executed_backend=STAGE/'native-controller/actually-loaded-sft-backend-private.py'
        if not executed_backend.exists():executed_backend=ROOT/'scripts/kali_curriculum_sft_jobs_20261117.py'
        assert sha(executed_backend)==runtime_freeze['runtime_source_sha256']['kali_curriculum_sft_jobs_20261117.py']
        assert sha(STAGE/'native-controller/config.json')==controller['config_sha256']==runtime_freeze['config_sha256']
        assert journal['task_hashes']==runtime_freeze['task_sha256']
        proxy=read(STAGE/'native-controller/task/setup_payload.json')['score_py']
        assert journal['grading_proxy_sha256']==hashlib.sha256(proxy.encode()).hexdigest()
        from kali_curriculum_native_facts_20261117 import require_completed_native_search
        require_completed_native_search(journal)
        assert journal['run_id'] == selection['native_run_id']
        assert selection['status'] == 'NATIVE_SEARCH_COMPLETE_SELECTION_FROZEN' and not selection['confirmation_used']
        assert set(selection['native_recipes']) == {'A1', 'A2'} and len(set(selection['native_recipes'].values())) == 2
        prior_state=None
        if controller.get('native_execution_mode')=='EXPLICIT_EXISTING_A1_PLUS_FRESH_A2':
            from kali_curriculum_recovery_bridge_20261117 import prior_candidate
            prior_state=prior_candidate()
            assert runtime_freeze['recovery_protocol_sha256']==sha(STAGE/'native-timeout-recovery-before-results-private.json')
        elif controller.get('native_execution_mode')=='EXPLICIT_EXISTING_A1_A2_REVALIDATION':
            from kali_curriculum_protocol_completion_bridge_20261117 import prior_candidate
            prior_state={cid:prior_candidate(cid) for cid in ['A1','A2']}
            assert runtime_freeze['recovery_protocol_sha256']==sha(STAGE/'both-existing-native-completion-protocol-private.json')
            assert runtime_freeze['protocol_failure_proof_sha256']==sha(STAGE/'native-protocol-recovery-before-A1-score-private.json')
            assert len(journal['private_full_events'])==sum(journal['event_counts'].values())
            import ast
            tree=ast.parse((STAGE/'native-controller/task/train_client.py').read_text())
            expected_readme=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ARTIFACT_README' for t in n.targets)))
            for index,cid in [(1,'A1'),(2,'A2')]:
                branch=next(a for a in journal['actions'] if a['target']=='search_1/complete_worker_'+str(index))
                files=journal['scored_outputs'][branch['output']['output_dir']]
                assert files['run.py']['sha256']==sha(STAGE/'native-controller/task/train_client.py')
                assert json.loads(files['train_metrics.json']['text'])==prior_state[cid]['training_receipt']
                assert files['README.md']['text']==expected_readme
        current_run_updates=validate_native_update_provenance(controller,selection,prior_state)
        for cid in ['A1', 'A2']:
            directory = STAGE/'runs'/cid; ex = read(directory/'execution-receipt.json'); launch = read(directory/'launch-freeze-private.json')
            assert ex['status'] == 'COMPLETE' and ex['worker_sha256'] == launch['config']['worker_sha256'] and ex['bundle_sha256'] == launch['config']['bundle_sha256']
            assert ex['official_TEST_queries'] == ex['confirmation_queries'] == 0
            audit_state(cid, directory, 'reasoning', selection['native_recipes'][cid])
            assert grade(scores[cid], scores['E0']) == read(directory/'score-private.json')['grade']
            provenance = controller['native_training_provenance'][cid]
            assert provenance['new_optimizer_steps_this_run']==current_run_updates[cid]
            dispatch = read(STAGE/'native-controller'/(cid+'-native-dispatch-private.json'))
            assert dispatch['run_id'] == journal['run_id'] and any('/worker_' in a for a in dispatch['active_actions'])
            if current_run_updates[cid]==0:
                assert dispatch['dispatch_kind']=='EXPLICIT_EXISTING_CHECKPOINT_REVALIDATION' and dispatch['new_optimizer_steps_this_run']==0
                assert dispatch['original_native_run_id']==provenance['original_native_run_id']
            changes[cid+'_minus_E0'] = paired_changes(scores[cid], scores['E0'])
        fixed = [(cid, canonical['results'][cid]['score']) for cid in ['E0', 'answer_only', 'reasoning'] if canonical['results'][cid]['eligible']]
        best_fixed = max(fixed, key=lambda a: a[1])
        available = selection['all_available_scores']
        assert tuple(available[0]) == best_fixed and len(available) == 3
        assert {cid for cid, value in available[1:]} == {'A1', 'A2'}
        for cid, value in available[1:]:
            assert abs(value-grade(scores[cid], scores['E0'])['score']) < 1e-8
        retained = max(available, key=lambda a: a[1])
        assert selection['candidate_id'] == retained[0] and abs(selection['DEV_score']-retained[1]) < 1e-8
        freeze = read(STAGE/'confirmation/selection-freeze-private.json')
        assert freeze['selection_sha256'] == sha(STAGE/'native-selection-private.json')
        confirmation_measurements = audit_confirmation_files(STAGE/'confirmation', STAGE, selection)
        confirmation = read(STAGE/'confirmation/analysis-private.json')
        from analyze_kali_curriculum_confirmation_20261117 import main as rescore_confirmation
        with contextlib.redirect_stdout(io.StringIO()):
            rescore_confirmation()
        assert read(STAGE/'confirmation/analysis-private.json') == confirmation, 'Confirmation rescoring changed results'
        assert confirmation['status'] == 'POST_SELECTION_CONFIRMATION_SCORED_NO_RESELECTION'
        assert not confirmation['retention_decision_changed_by_confirmation'] and confirmation['official_TEST_queries'] == 0
        assert read(STAGE/'confirmation/runs/execution-receipt.json')['status'] == 'COMPLETE'
        native = {k: selection[k] for k in ['candidate_id', 'native_selected_candidate', 'native_recipes', 'new_optimizer_steps_total']}
        native.update(execution_mode=controller.get('native_execution_mode','FRESH_TWO_CANDIDATES'),
                      new_optimizer_steps_by_candidate_in_completed_run=current_run_updates,
                      new_optimizer_steps_by_candidate_in_study={'A1':32,'A2':32})
    assert len(set(initialization)) == 1, 'Fresh LoRA initializations differ'
    save(STAGE/'changed-cases-private.json', changes)
    aggregate = {'status': 'FIXED_PAIR_AUDITED_NATIVE_PENDING' if args.fixed_only else 'FULL_INTERNAL_STUDY_AUDITED',
                 'audited_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'scoped_independent_teacher_rows': 23, 'strong_gaps': 3, 'replay_rows': 6,
                 'one_training_seed': True, 'inference_seeds': proto['seeds'],
                 'measurements': measurements,
                 'scores': {cid: (dict(grade(r, scores['E0']), eligible=True, score=0.) if cid == 'E0' else grade(r, scores['E0'])) for cid, r in scores.items()},
                 'changes': {k: v['aggregate'] for k, v in changes.items()}, 'native': native,
                 'confirmation': {k: v for k, v in confirmation.items() if k != 'details'} if confirmation else None,
                 'confirmation_measurements': confirmation_measurements,
                 'baseline_prefix_resume':{k:v for k,v in baseline_resume.items() if not k.startswith('private_')},
                 'official_TEST_queries': 0, 'raw_cases_exported': False,
                 'limitations': ['Scoped reference equivalence on internal panels; not official KaliBench accuracy.',
                                 'Three inference seeds do not replace independent training replicas.',
                                 'Reasoning and answer-only supervised tokens and answer weights differ.',
                                 'Two candidate ABA search uses twice one fixed candidate update budget.',
                                 'AI-reviewed traces and finite fixtures are not perfect semantic or expert verification.']}
    save(STAGE/('fixed-pair-audit-private.json' if args.fixed_only else 'final-audit-private.json'),
         {'aggregate': aggregate, 'evidence_sha256': hashes, 'initializations_identical': True})
    print(json.dumps({'status': aggregate['status'], 'states_audited': list(scores), 'official_TEST_queries': 0}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
