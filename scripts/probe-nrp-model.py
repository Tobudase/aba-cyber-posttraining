#!/usr/bin/env python3
"""Run a small, harmless NRP chat and function-call compatibility probe."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import ssl
import stat
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
KEY_FILE = ROOT / '.secrets/nrp_api_key'
BASE_URL = 'https://ellm.nrp-nautilus.io/v1'
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT = 30
TOTAL_TIMEOUT = 150
TOOL = {
    'type': 'function',
    'function': {
        'name': 'add_numbers',
        'description': 'Add two integers. This function performs no other action.',
        'parameters': {
            'type': 'object',
            'properties': {
                'a': {'type': 'integer', 'minimum': -1000, 'maximum': 1000},
                'b': {'type': 'integer', 'minimum': -1000, 'maximum': 1000},
            },
            'required': ['a', 'b'],
            'additionalProperties': False,
        },
    },
}


class ProbeError(Exception):
    """An error whose message is safe to include in the public report."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_token():
    token = os.environ.get('NRP_API_KEY', '').strip()
    if not token:
        try:
            fd = os.open(KEY_FILE, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            raise ProbeError('No token configured; use the existing private local setup flow.') from None
        except OSError:
            raise ProbeError('Cannot securely open credential file; symlinks are not accepted.') from None
        with os.fdopen(fd) as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise ProbeError('Credential file must be a regular file owned by the current user.')
            if stat.S_IMODE(info.st_mode) & 0o077:
                raise ProbeError('Credential file must be private (mode 600).')
            token = source.read(16385).strip()
    if not token or len(token) > 16384 or any(c.isspace() for c in token):
        raise ProbeError('Token is empty, too long, or contains whitespace.')
    return token


class Client:
    def __init__(self, token, disable_thinking=False):
        self.token = token
        self.disable_thinking = disable_thinking
        self.deadline = time.monotonic() + TOTAL_TIMEOUT
        context = ssl.create_default_context()
        if sys.platform == 'darwin' and ssl.get_default_verify_paths().cafile is None:
            system_ca = Path('/etc/ssl/cert.pem')
            if system_ca.is_file():
                context.load_verify_locations(cafile=str(system_ca))
        self.opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=context))
        self.generation_requests_attempted = 0

    def request(self, path, payload=None):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProbeError('Total probe time budget exhausted.')
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json'}
        data = None
        if payload is not None:
            if self.disable_thinking:
                payload = dict(payload, chat_template_kwargs={'enable_thinking': False})
            data = json.dumps(payload).encode()
            headers['Content-Type'] = 'application/json'
            self.generation_requests_attempted += 1
        req = urllib.request.Request(BASE_URL + path, data=data, headers=headers)
        try:
            with self.opener.open(req, timeout=min(REQUEST_TIMEOUT, remaining)) as response:
                body = bytearray()
                while True:
                    if time.monotonic() >= self.deadline:
                        raise ProbeError('Total probe time budget exhausted while reading response.')
                    chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - len(body)))
                    if not chunk:
                        break
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ProbeError('Response exceeded the 2 MiB size limit.')
            result = json.loads(body)
        except urllib.error.HTTPError as exc:
            raise ProbeError(f'HTTP {exc.code}; response body omitted; no redirect followed.') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ProbeError('Network or timeout failure; details omitted to protect credentials.') from None
        except (ValueError, UnicodeError):
            raise ProbeError('Endpoint returned invalid JSON; response body omitted.') from None
        if not isinstance(result, dict):
            raise ProbeError('Endpoint returned a non-object JSON response.')
        return result


def extract_response(payload):
    """Allowlist visible assistant content; never copy reasoning/analysis fields."""
    choices = payload.get('choices')
    if not isinstance(choices, list) or len(choices) != 1:
        raise ProbeError('Expected exactly one chat completion choice.')
    choice = choices[0]
    message = choice.get('message') if isinstance(choice, dict) else None
    if not isinstance(message, dict) or message.get('role') != 'assistant':
        raise ProbeError('Expected an assistant message.')
    content = message.get('content')
    if content is not None and not isinstance(content, str):
        raise ProbeError('Only text content is supported by this probe.')
    # Some deployments put reasoning in marked content instead of separate fields.
    # Omit the entire content in that case rather than persisting internal reasoning.
    suppressed = bool(content and re.search(r'<\s*/?\s*(?:think|analysis|reasoning)\b|\[/?(?:analysis|reasoning)\]|<\|(?:analysis|channel|im_start)\|>', content, re.I))
    visible = None if suppressed else content
    usage = payload.get('usage', {})
    safe_usage = {key: usage[key] for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')
                  if isinstance(usage, dict) and type(usage.get(key)) is int}
    return message, {
        'content': visible,
        'content_omitted_for_reasoning_marker': suppressed,
        'finish_reason': choice.get('finish_reason') if choice.get('finish_reason') in
                         ('stop', 'length', 'tool_calls', 'content_filter', 'function_call') else 'other',
        'usage': safe_usage,
    }


def validate_tool_call(message):
    calls = message.get('tool_calls')
    if not isinstance(calls, list) or len(calls) != 1:
        raise ProbeError('Expected exactly one add_numbers tool call; no function executed.')
    call = calls[0]
    if not isinstance(call, dict) or call.get('type') != 'function':
        raise ProbeError('Unexpected tool call type; no function executed.')
    call_id = call.get('id')
    fn = call.get('function')
    if not isinstance(call_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,256}', call_id):
        raise ProbeError('Missing or unsupported tool call ID; no function executed.')
    if not isinstance(fn, dict) or fn.get('name') != 'add_numbers':
        raise ProbeError('Unexpected function name; no function executed.')
    try:
        raw_args = fn.get('arguments')
        if not isinstance(raw_args, str) or len(raw_args) > 1024:
            raise ValueError
        args = json.loads(raw_args)
        if not isinstance(args, dict) or set(args) != {'a', 'b'}:
            raise ValueError
        if any(type(args[k]) is not int or not -1000 <= args[k] <= 1000 for k in args):
            raise ValueError
        if args != {'a': 7, 'b': 8}:
            raise ValueError
    except (ValueError, TypeError):
        raise ProbeError('Function arguments did not match the requested integers 7 and 8; no function executed.') from None
    clean = {'id': call_id, 'type': 'function', 'function': {
        'name': 'add_numbers', 'arguments': json.dumps(args, separators=(',', ':'))}}
    return clean, args['a'] + args['b']


def redact(value, token):
    if isinstance(value, str):
        return value.replace(token, '[REDACTED]')
    if isinstance(value, dict):
        return {key: redact(item, token) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, token) for item in value]
    return value


def run_probe(client, model, report):
    payload = client.request('/models')
    models = payload.get('data')
    if not isinstance(models, list) or model not in {
            item.get('id') for item in models if isinstance(item, dict) and isinstance(item.get('id'), str)}:
        raise ProbeError('Requested model was not present in the live /models response; no generation attempted.')
    report['model_listed'] = True
    ordinary = [{'role': 'user', 'content': 'What is 2 + 3? Reply with the numeral only.'}]
    report['stage'] = 'ordinary_question'
    message, result = extract_response(client.request('/chat/completions', {
        'model': model, 'messages': ordinary, 'max_tokens': 64, 'stream': False, 'n': 1}))
    result['passed'] = (result['content'] or '').strip() == '5' and not message.get('tool_calls')
    report['ordinary_question'] = result
    report['stage'] = 'tool_call'
    messages = [{'role': 'user', 'content': 'Use add_numbers exactly once with a=7 and b=8. After receiving its result, reply with the resulting numeral only.'}]
    message, result = extract_response(client.request('/chat/completions', {
        'model': model, 'messages': messages, 'tools': [TOOL],
        'tool_choice': {'type': 'function', 'function': {'name': 'add_numbers'}},
        'max_tokens': 256, 'stream': False, 'n': 1}))
    report['tool_call'] = result
    call, total = validate_tool_call(message)
    result.update({'passed': True, 'function': 'add_numbers', 'arguments': {'a': 7, 'b': 8}, 'local_result': total})
    # Reconstruct just the necessary public tool message; discard all extra fields.
    messages.extend([
        {'role': 'assistant', 'content': None, 'tool_calls': [call]},
        {'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps({'sum': total})},
    ])
    report['stage'] = 'tool_result_followup'
    message, result = extract_response(client.request('/chat/completions', {
        'model': model, 'messages': messages, 'tools': [TOOL], 'tool_choice': 'none',
        'max_tokens': 256, 'stream': False, 'n': 1}))
    result['passed'] = (result['content'] or '').strip() == str(total) and not message.get('tool_calls')
    report['tool_result_followup'] = result
    report['passed'] = all(report[key]['passed'] for key in
                           ('ordinary_question', 'tool_call', 'tool_result_followup'))
    report['stage'] = 'complete'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, help='Exact model ID from the current NRP /models list')
    parser.add_argument('--disable-thinking', action='store_true',
                        help='Use the documented enable_thinking=false option for Qwen/Gemma aliases')
    args = parser.parse_args()
    if len(args.model) > 256 or any(c.isspace() for c in args.model):
        parser.error('Use an exact model ID without whitespace (maximum 256 characters).')
    if args.disable_thinking and args.model not in {'qwen3', 'qwen3-small', 'gemma', 'gemma-small'}:
        parser.error('--disable-thinking is only verified in NRP documentation for qwen3/qwen3-small/gemma/gemma-small')
    try:
        token = read_token()
    except ProbeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    client = Client(token, disable_thinking=args.disable_thinking)
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'endpoint': BASE_URL,
              'model': args.model, 'stage': 'list_models', 'model_listed': False, 'passed': False,
              'disable_thinking': args.disable_thinking,
              'budget': {'generation_requests_max': 3, 'max_tokens_per_request': [64, 256, 256],
                         'request_timeout_seconds': REQUEST_TIMEOUT, 'total_budget_seconds': TOTAL_TIMEOUT},
              'task_execution': False, 'training_performed': False}
    try:
        run_probe(client, args.model, report)
    except ProbeError as exc:
        report['error'] = str(exc)
    report['generation_requests_attempted'] = client.generation_requests_attempted
    report = redact(report, token)
    dest = ROOT / 'docs/verification' / ('nrp-model-probe-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'passed': report['passed'], 'stage': report['stage'],
                      'generation_requests_attempted': client.generation_requests_attempted,
                      'report': str(dest), 'error': report.get('error')}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
