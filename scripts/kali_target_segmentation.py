"""Experimental same-text target segmentation; never change inference inputs.

This is an ablation, not the model's canonical training tokenizer. It makes no
claim about downstream reasoning-parser compatibility or generalization.
"""
import json


def encode_target_without_added_think_close(tokenizer, tokenizer_json, text):
    from tokenizers import Tokenizer

    closing = "</think>"
    if text.count(closing) != 1:
        raise ValueError("This reviewed experiment requires exactly one closing tag")
    ids = tokenizer.encode(closing, add_special_tokens=False)
    if len(ids) != 1:
        raise ValueError("Canonical tokenizer must have one dedicated closing token")
    token_id = ids[0]
    raw = json.loads(tokenizer_json)
    matches = [row for row in raw["added_tokens"] if row["id"] == token_id]
    if len(matches) != 1 or matches[0]["content"] != closing or closing in raw["model"]["vocab"]:
        raise ValueError("Unexpected model tokenizer; refuse implicit substitution")
    raw["added_tokens"] = [row for row in raw["added_tokens"] if row["id"] != token_id]
    alternative = Tokenizer.from_str(json.dumps(raw))
    output = alternative.encode(text, add_special_tokens=False).ids
    if token_id in output or tokenizer.eos_token_id in output:
        raise ValueError("Unexpected dedicated close or embedded EOS in target")
    if tokenizer.decode(output, skip_special_tokens=False, clean_up_tokenization_spaces=False) != text:
        raise ValueError("Target segmentation changed decoded text")
    return output
