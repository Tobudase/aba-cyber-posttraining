"""Source-verified Galleta argument rules on top of frozen v2 diagnostic.

v2 remains unchanged for its completed screen. This version is frozen before
new SFT outputs and is still reference equivalence, not full task execution.
"""
import json,re,shlex
from kali_reference_score_v2_20261117 import output_command,score as v2_score

def canonical_galleta(command):
    # A literal Bash ANSI-C newline argument only, not general shell expansion.
    command=re.sub(r"(?<=-d )\$'\\n'(?=\s|$)",lambda m:shlex.quote('\n'),command)
    argv=shlex.split(command)
    if not argv or argv[0]!='galleta':return command
    if len(argv)<2 or argv[-1].startswith('-'):raise ValueError('Galleta opens last argv as file')
    normalized=[]
    for token in argv:
        if token.startswith('-d') and token!='-d':normalized.extend(['-d',token[2:]])
        else:normalized.append(token)
    # Do not turn shell control into literal filenames during normalization.
    lex=shlex.shlex(command,posix=True,punctuation_chars=';&|<>');lex.whitespace_split=True;lex.commenters=''
    if any(t and all(c in ';&|<>' for c in t) for t in lex):raise ValueError('Shell syntax unsupported')
    return shlex.join(normalized)

def score(ref,text,finished=True):
    if ref.get('tool_name')!='galleta' and not ref['ground_truth_command'].startswith('galleta '):return v2_score(ref,text,finished)
    command=output_command(text,finished)
    if command is None:return v2_score(ref,text,finished)
    try:
        expected=canonical_galleta(ref['ground_truth_command']);actual=canonical_galleta(command)
        expected_args=shlex.split(expected);actual_args=shlex.split(actual)
        if not actual_args or actual_args[0]!='galleta':return {'status':'MISMATCH','reference_equal':False,'reason':'wrong_tool'}
        if actual_args[-1]!=expected_args[-1]:return {'status':'MISMATCH','reference_equal':False,'reason':'Galleta_uses_last_argv_as_input_filename'}
        return v2_score(dict(ref,ground_truth_command=expected),'<output>'+actual+'</output>',finished)
    except ValueError:return {'status':'UNKNOWN_EQUIVALENCE','reference_equal':False,'reason':'Galleta_parse_or_shell_syntax'}

