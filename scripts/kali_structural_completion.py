"""Opt-in TRAIN encoding for a fixed empty-think completion diagnostic.

This preserves the model's native input template. It does not synthesize reasoning,
repair answers, execute commands, or replace the historical continuation encoder.
Execution and explicit-constraint verification must precede this function.
"""
import re


def encode_structural_completion(tokenizer, row, messages, output_block, max_length=2048):
    if (row.get('split') != 'train' or row.get('training_eligible') is not True
            or row.get('official_test')):
        raise ValueError('Only explicitly eligible TRAIN rows allowed')
    if not all(row.get(k) is True for k in (
            'TRAIN_fixture_execution_verified', 'TRAIN_explicit_constraints_verified')):
        raise ValueError('Execution and explicit constraints must already be verified')
    if not messages or any(m.get('role') not in ('system', 'user') for m in messages):
        raise ValueError('Only input system/user messages allowed')
    match = re.fullmatch(r'<output>\s*([^<>]+?)\s*</output>', output_block, re.S)
    if not match or not match.group(1).strip():
        raise ValueError('Exactly one previously verified final command block required')
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    if not prompt.endswith('<think>'):
        raise ValueError('Native input template must retain its thinking prefix')
    completion = '\n</think>\n\n' + output_block
    prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
    target_ids = tokenizer.encode(completion, add_special_tokens=False)
    eos = tokenizer.eos_token_id
    if eos is None or not target_ids or eos in target_ids or not tokenizer.eos_token:
        raise ValueError('Completion must not contain an embedded EOS')
    ids = prompt_ids + target_ids + [eos]
    if len(ids) > max_length:
        raise ValueError('No silent sequence truncation')
    decoded = tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
    if decoded != prompt + completion + tokenizer.eos_token:
        raise ValueError('Token concatenation changed native text')
    return {'input_ids': ids, 'labels': [-100] * len(prompt_ids) + target_ids + [eos],
            'prompt_tokens': len(prompt_ids), 'target_tokens': len(target_ids) + 1}
