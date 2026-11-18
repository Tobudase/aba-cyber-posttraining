"""Validate a complete-batch prefix; reuse only the frozen original GPU code."""
import hashlib
import textwrap


def blocks(source):
    markers=['    proto=json.loads((a.stage/', '    allrows=[];began=time.monotonic()',
             '                batch=rows[off:', '                temp=a.output.with_suffix']
    assert all(source.count(m)==1 for m in markers),'Unexpected original evaluation source'
    setup=source[source.index(markers[0]):source.index(markers[1])]
    generation=source[source.index(markers[2]):source.index(markers[3])]
    assert 'torch.manual_seed(seed)' in generation and 'torch.inference_mode()' in generation
    assert 'model.generate(' in generation and 'allrows.append(' in generation
    return textwrap.dedent(setup),textwrap.dedent(generation),hashlib.sha256(generation.encode()).hexdigest()


def batches(rows,protocol):
    for seed in protocol['seeds']:
        for mode in protocol['modes']:
            for off in range(0,len(rows),protocol['batch_size']):
                yield seed,mode,off,rows[off:off+protocol['batch_size']]


def validate_prefix(data,rows,protocol,adapter_sha256,minimum=512):
    assert data['status'] in ['RUNNING','COMPLETE']
    assert data['adapter_sha256']==adapter_sha256
    expected=[];boundaries=set()
    for seed,mode,off,batch in batches(rows,protocol):
        expected.extend((r['id'],r['panel'],seed,mode,seed+off) for r in batch)
        boundaries.add(len(expected))
    predictions=data['predictions'];n=len(predictions)
    assert minimum<=n<=len(expected) and n in boundaries,'Only full original batches may be resumed'
    actual=[(r['id'],r['panel'],r['sampling_seed'],r['mode'],r['seed']) for r in predictions]
    assert actual==expected[:n] and len(set(actual))==n,'Prefix must be exact ordered unique seed/mode/task rows'
    for r in predictions:
        assert isinstance(r['response'],str) and isinstance(r['content'],str)
        assert r['finish_reason'] in ['stop','length'] and 0<=r['generated_tokens']<=protocol['max_new_tokens']
        if r['finish_reason']=='length':assert r['generated_tokens']==protocol['max_new_tokens']
    return n


def require_exact_first_batch(actual,expected):
    assert actual==expected,'First-batch replay differs; stop without accepting any prefix'
    return True
