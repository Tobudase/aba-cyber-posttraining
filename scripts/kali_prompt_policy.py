"""Explicit local inference policy; official thinking reproduction stays separate."""


def matched_final_only_prompt(tokenizer, messages):
    native = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    if not native.endswith('<think>'):
        raise ValueError('Unknown native prefix; refusing silent template substitution')
    final_only = native[:-len('<think>')]
    marker = 'KALI_PREFIX_BOUNDARY_271828'
    if any(marker in m['content'] for m in messages): raise ValueError('Marker collision')
    full = tokenizer.apply_chat_template(messages + [{'role': 'assistant', 'content': marker}],
                                         tokenize=False, add_generation_prompt=False)
    if full.count(marker) != 1 or full.split(marker)[0] != final_only:
        raise ValueError('Removed prefix differs from native SFT assistant boundary')
    return native, final_only


def generation_prompt(tokenizer, messages, policy='native'):
    if policy == 'native':
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    if policy == 'sft-aligned':
        return matched_final_only_prompt(tokenizer, messages)[1]
    raise ValueError('Unknown generation-prefix policy')
