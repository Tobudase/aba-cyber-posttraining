"""Check public aggregate arithmetic/hashes, without accessing private cases."""
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'results/kali-verified-teacher-stage-2026-11-17'


def main():
    manifest=json.loads((P/'final-manifest.json').read_text())
    assert not manifest['raw_cases_public'] and not manifest['weights_public']
    for name,digest in manifest['files'].items():
        path=P/name;assert path.resolve().is_relative_to(P.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
    result=json.loads((P/'final-results.json').read_text())
    assert result['status']=='FULL_INTERNAL_STUDY_AUDITED' and result['official_TEST_queries']==0
    assert result['scoped_independent_teacher_rows']==23 and result['original_low_success_gap_candidates']==3 and result['replay_rows']==6
    assert result['strictly_confirmed_gap_tasks']==1 and result['uncertain_gap_candidates']==2
    assert result['gap_evidence_correction']['unknown_is_not_certified_failure']
    assert result['one_training_seed'] and result['inference_seeds']==[3407,4407,5407]
    resume=result['baseline_prefix_resume']
    assert resume['status']=='EXACT_FROZEN_E0_PREFIX_RESUME_AUDITED'
    assert resume['reused_original_baseline_responses']==224 and resume['first_batch_replayed_identical_responses']==16
    assert resume['total_distinct_seed_mode_task_predictions']==624 and resume['original_attempt_SFT_optimizer_updates']==0
    assert resume['original_and_resumed_model_inputs_protocol_identical'] and not resume['SFT_training_reused']
    assert result['real_adapter_backup_verified'] and not result['raw_cases_exported']
    integrity=result['archived_adapter_integrity']
    assert set(integrity['states'])=={'answer_only','reasoning','A1','A2'}
    assert all(v['tensors']==144 and v['parameters']==7667712 and v['nonfinite_values']==0
               for v in integrity['states'].values())
    assert integrity['does_not_establish_training_benefit_or_GPU_failure_root_cause']
    sources=json.loads((P/'source/source-manifest.json').read_text())
    assert sources['status']==result['source_snapshot']['status']=='HASH_MATCHED_EXECUTED_SOURCE_SNAPSHOT'
    assert len(sources['files'])==result['source_snapshot']['source_files']
    assert not sources['private_cases_public'] and not sources['credentials_public'] and not sources['weights_public']
    assert not sources['standalone_public_dataset_reproduction']
    for name,record in sources['files'].items():
        path=P/'source'/name;assert path.resolve().is_relative_to((P/'source').resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
    for name,digest in result['executed_final_host_audit_source_sha256'].items():
        assert sources['files']['final-host-audit/'+name]['sha256']==digest
    for name,digest in result['executed_publication_source_sha256'].items():
        assert sources['files']['final-publication/'+name]['sha256']==digest
    budget=result['conservative_GPU_allocation_budget']
    tail=result.get('A2_deadline_prefix_continuation')
    assert budget['conservative_consumed_gpu_seconds']<=budget['stop_budget_gpu_seconds']==(26 if tail else 24)*3600
    if tail:
        assert tail['status']=='R6_ALL_COMMITTED_BATCHES_REUSED_EXACT_FIRST16_REPLAY_AND_MISSING_SUFFIX_VERIFIED'
        assert 416<=tail['retained_R6_prefix_responses']<624
        assert tail['retained_R6_prefix_responses']+tail['new_unique_tail_responses']==tail['distinct_scored_responses']==624
        assert tail['physical_first_batch_replay_responses']==16 and tail['additional_tail_GPU_attempts']==1
        assert tail['actual_R6_job_stays_failed'] and tail['original_numerical_setup_and_generation_blocks_unchanged']
        assert tail['new_optimizer_updates']==tail['confirmation_queries_at_amendment']==0 and not tail['A2_score_inspected_at_amendment']
        assert tail['study_ceiling_before_seconds']==24*3600 and tail['study_ceiling_after_seconds']==26*3600
        assert tail['ABA_ceiling_before_seconds']==9*3600 and tail['ABA_ceiling_after_seconds']==11*3600
        assert budget['operational_tail_amendment_sha256']==tail['activation_sha256']
    if 'A2_node_eviction_evaluation_replay' in result:
        replay=result['A2_node_eviction_evaluation_replay'];amend=result['A2_node_eviction_operational_amendment']
        assert replay['original_job_stays_failed'] and replay['new_optimizer_updates']==0
        assert replay['original_prediction_file_zero_bytes'] and replay['replayed_evaluation_responses']==624 and replay['reused_prediction_responses']==0
        assert replay['full_replay_GPU_attempts']==3 and replay['first_replay_GPU_attempt_stays_failed'] and replay['first_replay_completed_response_outputs']==0
        assert replay['failed_node_explicitly_excluded_from_completed_replay']
        assert replay['completed_GPU_was_in_original_allowed_list'] and replay['exact_original_adapter_reload_logit_probe_passed']
        assert replay['unassigned_A100_resource_fit_request_cancelled_GPU_seconds']==0
        hardware=result['A2_hardware_and_resource_amendments']
        assert hardware['originally_allowed_A100_80GB_attempted'] and hardware['extra_training_updates']==0
        assert hardware['unassigned_A6000_request_cancelled_GPU_seconds']==hardware['unassigned_oversized_A100_request_cancelled_GPU_seconds']==0
        assert not hardware['different_GPU_from_fixed_controls'] and hardware['final_resources']['nvidia.com/rtxa6000']=='1'
        assert hardware['A100_rejected_original_logit_fingerprint_before_any_completed_response']
        assert replay['A100_attempt_rejected_before_any_completed_response'] and replay['A100_original_logit_fingerprint_check_not_relaxed']
        assert hardware['final_resources']['cpu']=='500m'
        assert replay['unassigned_A6000_CPU_fit_request_cancelled_GPU_seconds']==0
        assert result['A2_CPU_fit_unassigned_request']['allocated_GPU_seconds']==0
        assert result['A2_CPU_fit_unassigned_request']['server_admission_dry_run_passed']
        assert hardware['final_resources']['memory']=='20Gi' and hardware['final_resources']['ephemeral-storage']=='24Gi'
        assert amend['new_training_candidates']==0 and amend['confirmation_queries']==0 and amend['study_GPU_ceiling_unchanged_seconds']==24*3600
        assert amend['ABA_allocation_ceiling_after_seconds']==9*3600
        assert budget['ABA_allocation_seconds']<=budget['ABA_stop_budget_seconds']==(11 if tail else 9)*3600
        if tail:assert replay['deadline_prefix_continuation']==tail
        if 'A2_same_Job_queue_window_amendment' in result:
            queue=result['A2_same_Job_queue_window_amendment']
            assert queue['old_Job_activeDeadlineSeconds']==12600 and queue['new_Job_activeDeadlineSeconds']==21600
            assert queue['Pod_GPU_runtime_seconds_UNCHANGED']==10800 and queue['queue_position_and_Job_Pod_UIDs_preserved']
            assert queue['new_optimizer_updates']==0
    else:assert budget['ABA_allocation_seconds']<=budget['ABA_stop_budget_seconds']==8*3600
    scores=result['scores'];assert set(scores)=={'E0','answer_only','reasoning','A1','A2'}
    assert hashlib.sha256((ROOT/'scripts/plot-kali-curriculum-final-20261118.py').read_bytes()).hexdigest()==result['public_plot_recipe_sha256']
    curves=result['conditional_command_CE_traces']
    assert set(curves)=={'answer_only','reasoning','A1','A2'}
    for cid,points in curves.items():
        assert len(points)==32 and [p['step'] for p in points]==list(range(1,33))
        assert all(set(p)=={'step','command_loss_monitor'} and math.isfinite(p['command_loss_monitor']) and p['command_loss_monitor']>=0 for p in points)
        measured=result['measurements'][cid]['training']
        assert abs(sum(p['command_loss_monitor'] for p in points[:4])/4-measured['first_epoch_command_loss'])<1e-10
        assert abs(sum(p['command_loss_monitor'] for p in points[-4:])/4-measured['last_epoch_command_loss'])<1e-10
    behavior=result['output_completion_behavior']
    assert behavior['status']=='ALL_FIVE_ENDPOINT_OUTPUT_BEHAVIOR_DESCRIBED'
    assert not behavior['references_or_correctness_labels_loaded'] and not behavior['selection_changed']
    assert behavior['new_model_calls']==behavior['official_TEST_queries']==behavior['confirmation_queries_added']==0
    assert set(behavior['states'])==set(scores)
    for cid,record in behavior['states'].items():
        total=record['all'];assert total['responses']==624
        assert total['truncated_with_one_nonempty_closed_output_tag']+total['truncated_without_one_nonempty_closed_output_tag']==total['truncated']
        assert total['generated_tokens']==sum(m['all']['generated_tokens'] for m in record['modes'].values())
        assert total['one_closed_output_tag_is_not_a_syntax_or_correctness_certificate']
        for mode,m in record['modes'].items():
            assert m['all']['responses']==312 and sum(p['responses'] for p in m['panels'].values())==312
            assert m['all']['truncated']==sum(p['truncated'] for p in m['panels'].values())
            for panel in ['development24','old64']:
                assert m['panels'][panel]['truncated']==scores[cid]['summary'][mode][panel]['truncated']
    for cid,score in scores.items():
        guards=[];lost=0
        for mode in ['thinking','nonthinking']:
            for panel,n in [('development24',24),('old64',64)]:
                s=score['summary'][mode][panel]
                assert s['unique_examples']==n and s['n']==n*3
                assert s['correct']==sum(score['per_seed'][str(seed)][mode][panel]['correct'] for seed in result['inference_seeds'])
                assert abs(s['mean_correct_per_seed']-s['correct']/3)<1e-10
                assert 0<=s['correct']<=s['n'] and 0<=s['invalid']<=s['n'] and 0<=s['truncated']<=s['n']
            for seed in result['inference_seeds']:
                seed=str(seed);r=score['retention'][seed][mode]
                b=scores['E0']['per_seed'][seed][mode];c=score['per_seed'][seed][mode]
                assert 0<=r['kept']<=r['base_correct']==b['old64']['correct']
                expected=bool(r['base_correct']) and r['kept']>=math.ceil(.95*r['base_correct']) and c['old64']['correct']>=b['old64']['correct'] and all(c[p]['invalid']<=b[p]['invalid'] and c[p]['truncated']<=b[p]['truncated'] for p in ['development24','old64'])
                assert r['guard_pass']==expected
                guards.append(expected);lost+=r['base_correct']-r['kept']
        delta=score['summary']['thinking']['development24']['mean_correct_per_seed']-scores['E0']['summary']['thinking']['development24']['mean_correct_per_seed']
        delta+=.001*(score['summary']['thinking']['old64']['mean_correct_per_seed']-scores['E0']['summary']['thinking']['old64']['mean_correct_per_seed'])
        assert abs(score['unpenalized_score']-delta)<1e-10
        if cid!='E0':
            assert score['eligible']==all(guards)
            assert abs(score['score']-(delta if all(guards) else -100-lost))<1e-10
            t=result['measurements'][cid]['training']
            assert t['updates']==t['nonzero_gradient_steps']==32
        else:assert score['eligible'] and score['score']==0
        assert result['measurements'][cid]['evaluation']['responses']==624
    native=result['native'];assert native['new_optimizer_steps_total']==64
    assert native['new_optimizer_steps_by_candidate_in_study']=={'A1':32,'A2':32}
    updates=native['new_optimizer_steps_by_candidate_in_completed_run']
    if native['execution_mode']=='EXPLICIT_EXISTING_A1_A2_REVALIDATION':
        assert updates=={'A1':0,'A2':0}
        history=result['prior_native_protocol_invalid_candidate']
        assert history['original_A1_framework_worker_output_failed'] is False
        assert history['original_A1_submitted_candidate_id']=='E0' and history['original_A1_submitted_optimizer_steps']==0
        assert history['original_A1_cannot_count_as_valid_trained_candidate_delivery']
        assert history['actual_original_native_dispatched_updates']=={'A1':32,'A2':32}
        assert history['completion_run_new_optimizer_updates']==updates
        assert not history['terminal_native_timeout_claimed']
        assert history['original_training_checkpoints_preserved_without_retraining']
        assert history['baseline_score_now_rejected_after_candidate_start']
    elif native['execution_mode']=='EXPLICIT_EXISTING_A1_PLUS_FRESH_A2':
        assert updates=={'A1':0,'A2':32}
        history=result['prior_native_worker_timeout']
        assert history['original_A1_optimizer_updates']==32 and history['original_Worker_remains_failed']
        assert history['original_GPU_evaluation_collected_without_retraining']
        assert history['A1_new_optimizer_updates_in_completed_native_run']==0
        assert history['A2_new_optimizer_updates_in_completed_native_run']==32
    else:
        assert native['execution_mode']=='FRESH_TWO_CANDIDATES' and updates=={'A1':32,'A2':32}
    assert result['native_run_provenance']['completed_run_new_optimizer_updates_by_candidate']==updates
    assert set(native['native_recipes'])=={'A1','A2'} and len(set(native['native_recipes'].values()))==2
    conf=result['confirmation'];assert conf['official_TEST_queries']==0 and not conf['retention_decision_changed_by_confirmation']
    if 'confirmation_deadline_continuation' in result:
        ct=result['confirmation_deadline_continuation']
        assert ct['status']=='SAME_FROZEN_CONFIRMATION_COHORT_AND_ALL_PREFIXES_AUDITED_AFTER_ACTUAL_DEADLINE'
        assert ct['original_job_stays_FAILED'] and ct['same_selected_models_cohort_seeds_numeric_code_and_scoring']
        assert ct['all_committed_outputs_retained_without_quality_selection'] and not ct['selection_changed']
        assert ct['unique_confirmation_tasks']==24 and ct['unique_confirmation_responses']==576 and ct['unique_already_TRAIN_gap_responses']==72
        for stream,n in [('confirmation',576),('already_TRAIN_gap',72)]:
            assert ct['counts_by_stream'][stream]['retained']+ct['counts_by_stream'][stream]['new']==n
        assert ct['additional_tail_GPU_jobs']==1 and ct['new_training_updates']==ct['new_training_candidates']==ct['official_TEST_queries']==0
        assert not ct['confirmation_scores_inspected_before_activation']
        assert ct['original_TRAIN_probe_passed_before_original_queries'] and ct['all_adapter_original_TRAIN_probes_passed_before_tail']
        assert ct['tail_Pod_seconds']==6600 and ct['tail_Job_seconds']==8400 and ct['study_GPU_ceiling_seconds_unchanged']==26*3600
    assert result['confirmation_pre_query_TRAIN_receipt_probes']['all_selected_adapters_verified_before_first_confirmation_question']
    assert conf['confirmation_unique_tasks']==24
    for state,summary in conf['summary'].items():
        for mode,s in summary.items():
            assert s['unique_tasks']==24 and s['inference_samples']==72
            assert s['correct']==sum(v['correct'] for v in s['per_seed'].values())
            assert abs(s['mean_correct_per_seed']-s['correct']/3)<1e-10
    aliases=conf['aliases'];r=aliases.get('fixed_reasoning','fixed_reasoning');a=aliases.get('fixed_answer_only','fixed_answer_only')
    for mode in ['thinking','nonthinking']:
        d=conf['summary'][r][mode]['mean_correct_per_seed']-conf['summary'][a][mode]['mean_correct_per_seed']
        assert abs(d-conf['paired']['reasoning_minus_answer'][mode]['mean_correct_count_difference'])<1e-9
    fit=result['trainfit'];assert fit['false_passed_negative_controls']==0 and fit['GPU']==0
    main_audit=result['main_TRAIN_fixture_execution_audit']
    assert main_audit['status']=='ACTUAL_MAIN_TRAIN_AND_GAP_CPU_EXECUTION_AND_PREDICTION_MAPPING_AUDITED'
    assert main_audit['actual_CPU_jobs_succeeded']==1 and main_audit['unique_fixture_tasks']==fit['unique_fixture_tasks']
    assert main_audit['unique_main_TRAIN_fit_tasks']==10 and main_audit['known_TRAIN_gap_tasks']==3
    assert main_audit['overlap_main_fit_and_gap_tasks']==1 and main_audit['unique_fixture_tasks']==12
    assert main_audit['reference_positive_checks']==fit['reference_positive_checks'] and main_audit['negative_controls']==fit['negative_controls']
    assert main_audit['false_passed_negative_controls']==main_audit['GPU']==main_audit['new_model_calls']==main_audit['protected_DEV_confirmation_TEST_commands']==0
    assert not main_audit['selection_changed'] and main_audit['task_postconditions_unchanged']
    assert main_audit['raw_commands_traceable_to_exact_frozen_predictions'] and main_audit['complete_analysis_recomputed_identically']
    assert main_audit['all_negative_controls_explicit_FAIL']
    assert main_audit['audit_source_sha256']==sources['files']['main-TRAIN-and-gap-fixtures/audit_kali_curriculum_main_fit_20261118.py']['sha256']
    replay_fit=result['publisher_TRAIN_replay_fit']
    assert replay_fit['status']=='ACTUAL_CPU_JOBS_AND_ALL_FIVE_REPLAY_FIT_RESULTS_AUDITED'
    assert set(replay_fit['summary'])==set(scores)
    assert replay_fit['unique_seen_TRAIN_tasks']==6 and replay_fit['samples_per_mode_per_state']==18
    assert replay_fit['reference_positive_checks_across_two_batches']==24 and replay_fit['negative_controls_across_two_batches']==32
    assert replay_fit['false_passed_negative_controls']==replay_fit['GPU']==replay_fit['new_model_calls']==replay_fit['protected_DEV_confirmation_TEST_commands']==0
    assert not replay_fit['selection_changed'] and replay_fit['same_exact_commands_retried_after_quotation_safety_fix']
    assert replay_fit['actual_cpu_jobs_succeeded']==2 and replay_fit['actual_cpu_job_failed_retained']==1
    for modes in replay_fit['summary'].values():
        for row in modes.values():
            assert row['unique_training_tasks']==6 and row['inference_samples']==18
            assert sum(row[k] for k in ['functional_pass','functional_fail','unknown','invalid_output'])==18
            assert row['functional_pass']==sum(s['functional_pass'] for s in row['per_seed'].values())
            assert row['unbalanced_shell_quotation']<=row['unknown']
    assert fit['paired_fixture_controls_verified'] and fit['unique_fixture_tasks']>0
    assert fit['reference_positive_checks']==2*fit['unique_fixture_tasks']
    assert fit['negative_controls']>=fit['reference_positive_checks']
    for state,summary in fit['summary'].items():
        for mode,s in summary.items():
            assert s['functional_pass']+s['functional_fail']+s['invalid_output']+s['unknown']==s['inference_samples']
    objective=result['supervision_objective_composition']
    assert objective['not_measured_gradient_share'] and objective['exposure_order_updates_unchanged']
    for arm,s in objective['arms'].items():
        steps=s['anonymous_update_denominators'];assert len(steps)==32
        assert sum(x['total_target_tokens'] for x in steps)==8*s['all_target_tokens_per_epoch']
        assert sum(x['replay_target_tokens'] for x in steps)==8*s['replay_target_tokens_per_epoch']==984
        assert abs(s['sample_replay_fraction']-6/29)<1e-12
        assert abs(s['global_replay_token_fraction']-123/s['all_target_tokens_per_epoch'])<1e-12
        assert abs(s['mean_update_replay_token_coefficient_fraction']-sum(x['replay_target_tokens']/x['total_target_tokens'] for x in steps)/32)<1e-12
    prefix=result['teacher_forced_prefix_command_exposure']
    assert prefix['independent_teacher_rows']==prefix['reasoning_contains_verbatim_final_command']==23
    for state,modes in result['previously_repeated_failure_single_TRAIN_task_fit'].items():
        assert state.startswith('known_gap_')
        for s in modes.values():
            assert s['unique_training_tasks']==1 and s['inference_samples']==3
            assert s['functional_pass']+s['functional_fail']+s['unknown']+s['invalid_output']==3
    print('PASS: public hashes, actual-update aggregate receipts, paired-seed arithmetic, retention guards and confirmation; private cases not reexecuted by this verifier.')


if __name__=='__main__':main()
