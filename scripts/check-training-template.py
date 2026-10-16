#!/usr/bin/env python3
"""CPU-only checks of pinned tokenization and assistant masks using synthetic tools."""
import os
os.environ['USE_TORCH'] = '0'
os.environ['USE_TF'] = '0'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]


def main():
    lock = json.loads((ROOT / 'configs/student-model.lock.json').read_text())
    cache = ROOT / lock['local_tokenizer_dir']
    for name, info in lock['files'].items():
        if hashlib.sha256((cache / name).read_bytes()).hexdigest() != info['sha256']:
            raise RuntimeError('Tokenizer/config checksum mismatch: ' + name)
    template_lock = json.loads((ROOT / 'configs/training-template.lock.json').read_text())
    path = ROOT / 'configs/templates/qwen3_training.jinja'
    if hashlib.sha256(path.read_bytes()).hexdigest() != template_lock['templates'][path.name]['sha256']:
        raise RuntimeError('Training template checksum mismatch')
    tokenizer = AutoTokenizer.from_pretrained(cache, local_files_only=True, trust_remote_code=False)
    if not tokenizer.is_fast:
        raise RuntimeError('Offset checks require fast tokenizer')
    original = tokenizer.chat_template
    template = path.read_text()
    tools = [{'type': 'function', 'function': {'name': 'echo_text',
              'description': 'TOOL_SCHEMA_SENTINEL_11',
              'parameters': {'type': 'object', 'properties': {'text': {'type': 'string'}},
                             'required': ['text'], 'additionalProperties': False}}}]
    messages = [
        {'role': 'system', 'content': 'SYSTEM_SENTINEL_00'},
        {'role': 'user', 'content': 'USER_SENTINEL_01'},
        {'role': 'assistant', 'content': None, 'tool_calls': [
            {'type': 'function', 'id': 'call_echo', 'function': {'name': 'echo_text',
             'arguments': {'text': 'ASSISTANT_ARGUMENT_SENTINEL_33'}}}]},
        {'role': 'tool', 'tool_call_id': 'call_echo', 'content': 'TOOL_RESULT_SENTINEL_22'},
        {'role': 'assistant', 'content': 'ASSISTANT_FINAL_SENTINEL_44'},
    ]
    fixtures = [('single_tool', messages), ('second_user_turn', messages + [
        {'role': 'user', 'content': 'SECOND_USER_SENTINEL_55'},
        {'role': 'assistant', 'content': 'SECOND_ASSISTANT_SENTINEL_66'}])]
    results = []
    for name, conversation in fixtures:
        encoded = tokenizer.apply_chat_template(conversation, tools=tools, chat_template=template,
            tokenize=True, return_dict=True, return_assistant_tokens_mask=True,
            add_generation_prompt=False, enable_thinking=False)
        text = tokenizer.apply_chat_template(conversation, tools=tools, chat_template=template,
            tokenize=False, add_generation_prompt=False, enable_thinking=False)
        direct = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        ids, mask = encoded['input_ids'], encoded['assistant_masks']
        if ids != direct['input_ids'] or len(ids) != len(mask) or not any(mask):
            raise RuntimeError('Tokenization/mask consistency failure')
        checks = {}
        for marker, expected in [('SYSTEM_SENTINEL_00', 0), ('USER_SENTINEL_01', 0),
                                 ('TOOL_SCHEMA_SENTINEL_11', 0), ('TOOL_RESULT_SENTINEL_22', 0),
                                 ('ASSISTANT_ARGUMENT_SENTINEL_33', 1), ('ASSISTANT_FINAL_SENTINEL_44', 1),
                                 ('SECOND_USER_SENTINEL_55', 0), ('SECOND_ASSISTANT_SENTINEL_66', 1)]:
            if marker not in text:
                if marker.startswith('SECOND_') and name == 'single_tool':
                    continue
                raise RuntimeError('Missing fixture marker: ' + marker)
            start, end = text.index(marker), text.index(marker) + len(marker)
            positions = [i for i, (a, b) in enumerate(direct['offset_mapping']) if b > start and a < end]
            if not positions or any(mask[i] != expected for i in positions):
                raise RuntimeError('Loss mask incorrectly covers marker: ' + marker)
            checks[marker] = {'expected_mask': expected, 'tokens_checked': len(positions)}
        # A tool response must not rewrite the preceding assistant/tool-call prefix.
        a = tokenizer.apply_chat_template(conversation[:3], tools=tools, chat_template=template,
            tokenize=False, add_generation_prompt=False, enable_thinking=False)
        b = tokenizer.apply_chat_template(conversation[:4], tools=tools, chat_template=template,
            tokenize=False, add_generation_prompt=False, enable_thinking=False)
        if not b.startswith(a):
            raise RuntimeError('Training template rewrites assistant prefix when appending tool result')
        original_text = tokenizer.apply_chat_template(conversation, tools=tools, chat_template=original,
            tokenize=False, add_generation_prompt=False, enable_thinking=False)
        results.append({'fixture': name, 'tokens': len(ids), 'assistant_loss_tokens': sum(mask),
                        'masked_context_tokens': len(mask) - sum(mask), 'checks': checks,
                        'tool_response_preserves_training_prefix': True,
                        'training_and_original_render_identical': text == original_text,
                        'training_render_sha256': hashlib.sha256(text.encode()).hexdigest()})
    # Left padding is not used here. Any future collator must keep padding labels at -100.
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'PASSED',
              'model_id': lock['model_id'], 'revision': lock['revision'],
              'runtime': {name: version(name) for name in ['transformers', 'tokenizers', 'jinja2']},
              'training_template': str(path.relative_to(ROOT)),
              'template_source': {'package': 'trl', 'version': template_lock['version']},
              'original_template_has_generation_tags': lock['official_template_has_generation_tags'],
              'fixtures': results, 'model_weights_loaded': False, 'gpu_used': False,
              'training_executed': False, 'synthetic_fixture_only': True,
              'limitations': ['Validated tokenizer masks only, not Trainer data collator, GPU runtime or model learning.',
                             'TRL training variant keeps empty think blocks in prior assistant turns; it intentionally differs from the inference template.',
                             'No hidden reasoning generated or collected; empty think tags are structural tokens.',
                             'Long real trajectories, parallel tools and truncation still need data-dependent validation.']}
    dest = ROOT / 'docs/verification/training-template-check.json'
    dest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'report': str(dest),
                      'fixtures': [{k: f[k] for k in ['fixture', 'tokens', 'assistant_loss_tokens',
                                   'masked_context_tokens']} for f in results], 'gpu_used': False}, indent=2))


if __name__ == '__main__':
    main()
