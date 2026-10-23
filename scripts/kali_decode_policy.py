"""Preserve complete native token decoding and explicitly audit MLX rendering."""


def audit_stream_text(decoded, streamed):
    if decoded == streamed:
        return 'EXACT'
    # mlx_lm.BPEStreamingDetokenizer._maybe_trim_space removes one initial ASCII
    # space. Preserve it in canonical response; never silently fix command text.
    if decoded.startswith(' ') and decoded[1:] == streamed:
        return 'MLX_STREAM_DROPPED_ONE_INITIAL_ASCII_SPACE'
    raise ValueError('Unexplained stream/token decode mismatch')
