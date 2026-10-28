#!/usr/bin/env python3
"""Bounded structured NRP proposal via forced Anthropic tool call."""
import hashlib
import json
import os
from pathlib import Path
import ssl
import stat
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/verification/kali-next-data-pilot-2026-10-27/anthropic-tool-proposal'
PROMPT = ('Create exactly three distinct read-only jq analysis tasks for a synthetic '
          'events.json file with events[] and id, severity, src, bytes, proto fields. '
          'Use intents low_ids, max_bytes, and unique_protocols once each. Each item '
          'needs a clear English question and one jq command reading events.json. '
          'No network, writing, shell operators, or other files. Submit the candidates '
          'to the tool. These are untrusted proposals, not gold labels.')
URL = 'https://ellm.nrp-nautilus.io/anthropic/v1/messages'
TOOL = {'name': 'submit_candidates', 'description': 'Return proposed synthetic training tasks.',
        'input_schema': {'type': 'object', 'properties': {'candidates': {
            'type': 'array', 'items': {'type': 'object', 'properties': {
                'intent': {'type': 'string'}, 'question': {'type': 'string'},
                'command': {'type': 'string'}},
                'required': ['intent', 'question', 'command']}}}, 'required': ['candidates']}}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    assert not OUT.exists(), 'Do not overwrite a proposal attempt'
    OUT.mkdir(parents=True)
    key_file = ROOT / '.secrets/nrp_api_key'
    assert key_file.is_file() and not key_file.is_symlink()
    assert stat.S_IMODE(key_file.stat().st_mode) & 0o077 == 0
    token = key_file.read_text().strip()
    assert token and not any(c.isspace() for c in token)
    receipt = {'requested_at': datetime.now(timezone.utc).isoformat(),
               'endpoint': URL, 'model': 'qwen3-small', 'timeout_seconds': 75,
               'max_tokens': 1600, 'prompt_sha256': hashlib.sha256(PROMPT.encode()).hexdigest(),
               'public_context_only': True, 'protected_examples_sent': 0,
               'credential_recorded': False, 'native_ABA_generation': False}
    payload = {'model': 'qwen3-small', 'max_tokens': 1600, 'temperature': 0.1,
               'messages': [{'role': 'user', 'content': PROMPT}], 'tools': [TOOL],
               'tool_choice': {'type': 'tool', 'name': 'submit_candidates'}}
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + token, 'anthropic-version': '2023-06-01',
                 'Content-Type': 'application/json', 'Accept': 'application/json'})
    context = ssl.create_default_context()
    if os.uname().sysname == 'Darwin' and ssl.get_default_verify_paths().cafile is None:
        context.load_verify_locations(cafile='/etc/ssl/cert.pem')
    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=context))
    stage = 'network'
    try:
        with opener.open(req, timeout=75) as response:
            raw = response.read(300_001)
        stage = 'size'
        assert len(raw) <= 300_000
        result = json.loads(raw)
        receipt['response_type'] = result.get('type')
        receipt['response_role'] = result.get('role')
        receipt['stop_reason'] = result.get('stop_reason')
        stage = 'envelope'
        assert result.get('type') == 'message' and result.get('role') == 'assistant'
        blocks = result.get('content')
        stage = 'blocks'
        assert isinstance(blocks, list)
        receipt['content_block_types'] = [b.get('type') for b in blocks if isinstance(b, dict)]
        selected = [b for b in blocks if isinstance(b, dict) and b.get('type') == 'tool_use'
                    and b.get('name') == 'submit_candidates']
        stage = 'tool_use'
        assert len(selected) == 1 and isinstance(selected[0].get('input'), dict)
        candidates = selected[0]['input'].get('candidates')
        stage = 'candidate_shape'
        assert isinstance(candidates, list) and len(candidates) == 3
        assert all(isinstance(x, dict) and all(isinstance(x.get(k), str)
                   for k in ('intent', 'question', 'command')) for x in candidates)
        (OUT / 'candidates-private.json').write_text(json.dumps(candidates, indent=2) + '\n')
        receipt.update(status='CANDIDATES_SAVED_PRIVATE', candidate_count=len(candidates),
                       candidates_sha256=hashlib.sha256((OUT / 'candidates-private.json').read_bytes()).hexdigest(),
                       usage=result.get('usage'))
    except urllib.error.HTTPError as exc:
        receipt.update(status='HTTP_ERROR', http_status=exc.code, failure_stage=stage)
    except Exception as exc:
        receipt.update(status='REJECTED_RESPONSE', error_type=type(exc).__name__, failure_stage=stage)
    (OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: receipt.get(k) for k in ('status', 'http_status', 'error_type',
          'failure_stage', 'response_type', 'stop_reason', 'content_block_types', 'candidate_count')}))


if __name__ == '__main__':
    main()
