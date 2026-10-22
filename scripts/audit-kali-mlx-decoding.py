#!/usr/bin/env python3
"""Bounded4-case token/stream/repeated-output audit; not additional model selection."""
from datetime import datetime, timezone
import gc
import json
import signal

from benchkit import ROOT, load_jsonl, load_manifest, load_tokenizer, sha, write_json


def main():
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    mx.set_memory_limit(9 * 1024**3); mx.set_cache_limit(256 * 1024**2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Decoding audit deadline')))
    signal.alarm(180)
    conversion = json.loads((ROOT / 'docs/verification/kali-mlx-convert.json').read_text())
    _, records = load_manifest(ROOT / 'data/benchkit/kali-external-dev/manifest.json', 'dev_search')
    rows = {r['id']: r for r in records}; native = load_tokenizer('redsage')
    audit = []
    for phase, identifiers, adapter in [
        ('E0', ['authored-doc-v1-certificate-serial-01', 'authored-doc-v1-wc-lines-01'], None),
        ('E1', ['authored-doc-v1-certificate-serial-03', 'authored-doc-v1-head-five-02'],
         ROOT / 'docs/verification/kali-mlx-e1-train-2026-10-22/adapter')]:
        old_path = ROOT / ('docs/verification/kali-mlx-e0-2026-10-22' if phase == 'E0' else 'docs/verification/kali-mlx-e1-dev-2026-10-22') / 'predictions.jsonl'
        old = {r['id']: r for r in load_jsonl(old_path)}
        model, tokenizer = load(conversion['directory'], adapter_path=str(adapter) if adapter else None,
            tokenizer_config={'trust_remote_code': False, 'fix_mistral_regex': False})
        model.eval()
        for identifier in identifiers:
            prompt = native.apply_chat_template(rows[identifier]['messages'], tokenize=False, add_generation_prompt=True)
            ids = native.encode(prompt, add_special_tokens=False)
            mx.random.seed(42); generated = []; segments = []
            for result in stream_generate(model, tokenizer, prompt=ids, max_tokens=1024,
                sampler=make_sampler(temp=0), prefill_step_size=256):
                segments.append(result.text)
                if result.finish_reason != 'stop': generated.append(int(result.token))
            raw = native.decode(generated, skip_special_tokens=False, clean_up_tokenization_spaces=False)
            text = ''.join(segments)
            if raw != text or text != old[identifier]['response']:
                raise ValueError('Raw-token/stream/repeated output mismatch: ' + identifier)
            audit.append({'phase': phase, 'id': identifier, 'generated_token_ids': generated,
                'response': text, 'raw_decode_matches_stream': True,
                'matches_recorded_prediction': True, 'original_predictions_sha256': sha(old_path.read_bytes())})
        del model, tokenizer
        gc.collect(); mx.clear_cache()
    signal.alarm(0)
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'FOUR_CASE_DECODING_AND_REPLAY_AUDIT_PASSED',
        'rows': audit, 'new_generation_calls': 4, 'model_selection_performed': False,
        'official_test_rows': 0, 'confirmation_rows': 0,
        'meaning': 'Missing opening tags and dropped openssl in sampled outputs are model outputs, not streaming text loss.'}
    write_json(ROOT / 'docs/verification/kali-mlx-decoding-audit-2026-10-22.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, indent=2))


if __name__ == '__main__': main()
