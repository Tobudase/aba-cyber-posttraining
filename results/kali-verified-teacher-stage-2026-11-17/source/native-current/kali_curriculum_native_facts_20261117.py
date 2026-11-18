"""Read terminal native facts correctly; recoverable events are not outcomes."""
import hashlib
import json

A1_WORKER='search_1/complete_worker_1/worker_1'


def actual_worker_timeout(journal):
    # Normal Clock expiry is ActionCompleted(Failure), NOT necessarily an
    # ExecutionFailureRecorded event (that event represents recoverable faults).
    completed=[a for a in journal['actions'] if a['target']==A1_WORKER]
    assert len(completed)<=1, 'Ambiguous Worker action history'
    return bool(completed and completed[0]['output'].get('failed') is True
                and completed[0]['output'].get('kind')=='timeout')


def require_two_scored_native_candidates(journal):
    files_required={'run.py','README.md','train_metrics.json','final_model/model.json'}
    for index,cid in [(1,'A1'),(2,'A2')]:
        composite='search_1/complete_worker_'+str(index)
        for target in [composite,composite+'/worker_1']:
            matches=[a for a in journal['actions'] if a['target']==target]
            assert len(matches)==1 and matches[0]['output'].get('failed') is False, 'Both real Worker and complete-candidate actions must succeed'
        complete=next(a for a in journal['actions'] if a['target']==composite)['output']
        directory=complete['output_dir']
        assert directory in journal['scored_outputs'], 'Candidate must have a successful native Score Program output'
        files=journal['scored_outputs'][directory]
        assert set(files)==files_required
        for record in files.values():
            assert hashlib.sha256(record['text'].encode()).hexdigest()==record['sha256']
        pointer=json.loads(files['final_model/model.json']['text'])
        assert pointer['candidate_id']==cid, 'Actual scored candidate differs from assigned native branch'
    return True


def require_completed_native_search(journal):
    """Recovered execution events do not replace terminal action evidence."""
    assert journal['head']['result']=='completed','Native search head must actually complete'
    require_two_scored_native_candidates(journal)
    return {'successful_required_candidates':2,'recoverable_execution_failure_events':len(journal.get('failures',[]))}
