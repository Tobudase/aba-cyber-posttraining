"""Verify published interim hashes/arithmetic; no private cases or GPU required."""
import hashlib,json,math
from pathlib import Path

P=Path(__file__).resolve().parents[1]/'results/kali-verified-teacher-stage-2026-11-17'

def main():
    manifest=json.loads((P/'recovery-interim-manifest.json').read_text())
    for name,digest in manifest.items():
        path=P/name;assert path.resolve().is_relative_to(P.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
    d=json.loads((P/'recovery-interim.json').read_text());scores=d['scores']
    assert d['status']=='INTERIM_FIXED_AND_A1_AUDITED_A2_NATIVE_CONFIRMATION_PENDING'
    assert not d['native_ABA_completed_and_validated'] and not d['post_selection_confirmation_complete']
    assert not d['A2_complete_evaluation_available'] and d['A2_has_no_score'] and 'A2' not in scores
    assert d['official_TEST_queries']==0 and not d['raw_cases_public'] and not d['weights_public']
    assert d['retained_model']=='E0' and d['inference_seeds']==[3407,4407,5407] and d['training_seeds']==[3407]
    assert d['actual_verified_optimizer_updates_by_independent_adapter']=={'answer_only':32,'reasoning':32,'A1':32,'A2':32}
    for state,score in scores.items():
        guards=[];lost=0
        for mode in ['thinking','nonthinking']:
            for panel,n in [('development24',24),('old64',64)]:
                row=score['summary'][mode][panel]
                assert row['n']==3*n and row['unique_examples']==n
                assert row['correct']==sum(score['per_seed'][str(seed)][mode][panel]['correct'] for seed in d['inference_seeds'])
                assert abs(row['mean_correct_per_seed']-row['correct']/3)<1e-12
            for seed in d['inference_seeds']:
                seed=str(seed);r=score['retention'][seed][mode];base=scores['E0']['per_seed'][seed][mode];s=score['per_seed'][seed][mode]
                expected=bool(r['base_correct']) and r['kept']>=math.ceil(.95*r['base_correct']) and s['old64']['correct']>=base['old64']['correct'] and all(s[p]['invalid']<=base[p]['invalid'] and s[p]['truncated']<=base[p]['truncated'] for p in ['development24','old64'])
                assert expected==r['guard_pass'];guards.append(expected);lost+=r['base_correct']-r['kept']
        delta=score['summary']['thinking']['development24']['mean_correct_per_seed']-scores['E0']['summary']['thinking']['development24']['mean_correct_per_seed']
        delta+=.001*(score['summary']['thinking']['old64']['mean_correct_per_seed']-scores['E0']['summary']['thinking']['old64']['mean_correct_per_seed'])
        assert abs(score['unpenalized_score']-delta)<1e-10
        if state=='E0':assert score['eligible'] and score['score']==0
        else:assert not score['eligible'] and not all(guards) and score['score']==-100-lost
    infrastructure=d['A2_infrastructure']
    assert infrastructure['original_prediction_file_bytes_after_recovery']==0 and infrastructure['original_response_contents_reused']==0
    assert infrastructure['first_replay_completed_response_outputs']==0 and infrastructure['extra_training_updates']==0
    assert infrastructure['original_adapter_nonfinite_parameters']==0 and not infrastructure['CUDA_kernel_or_hardware_root_cause_proven']
    print('PASS: interim hashes, paired-seed arithmetic and retention; A2/native/confirmation remain explicitly incomplete. Private cases not re-executed.')

if __name__=='__main__':main()
