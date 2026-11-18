"""Versioned reference equivalence diagnostic, not arbitrary command semantics.

Preserves option-value bindings, positional order, quotes, duplicate counts and
rejects shell operators. Unsupported spellings are unresolved, not functional
FAIL. Native KaliBench remains independently reported.
"""
import collections,json,re,shlex

def output_command(text,finished=True):
    if not finished:return None
    matches=re.findall(r'<output>\s*([\s\S]*?)\s*</output>',text)
    if len(matches)!=1 or text.count('<output>')!=1 or text.count('</output>')!=1:return None
    return matches[0].strip() or None

def _optional(ref):
    opts=ref.get('optional_args') or {}
    return json.loads(opts) if isinstance(opts,str) else opts

def _parse(command,ref):
    lexer=shlex.shlex(command,posix=True,punctuation_chars=';&|<>');lexer.whitespace_split=True;lexer.commenters=''
    tokens=list(lexer)
    if not tokens:return None,'EMPTY'
    if any(t and all(c in ';&|<>' for c in t) for t in tokens):return None,'SHELL_OPERATOR_UNSUPPORTED'
    opts=_optional(ref);aliases={a:key for key in opts for a in key.split('|')}
    # The sole extra alias is supported by fixed LLVM14 official Options.td.
    if tokens[0]=='dsymutil':
        key=next((k for k in opts if '--update' in k.split('|')),None)
        if key is not None:aliases['-update']=key
    groups=collections.Counter();positionals=[];i=1;endopts=False
    while i<len(tokens):
        t=tokens[i]
        if t=='--' and not endopts:endopts=True;i+=1;continue
        flag,sep,value=t.partition('=')
        if not endopts and flag in aliases:
            key=aliases[flag]
            if opts[key] is not None:
                if not sep:
                    i+=1
                    if i==len(tokens):return None,'MISSING_VALUE'
                    value=tokens[i]
            else:
                if sep:return None,'FLAG_UNEXPECTED_VALUE'
                value=None
            groups[(key,value)]+=1
        elif not endopts and t.startswith('-') and t!='-':return None,'UNSUPPORTED_OPTION_SPELLING'
        else:positionals.append(t)
        i+=1
    return (tokens[0],groups,positionals),None

def score(ref,text,finished=True):
    command=output_command(text,finished)
    if command is None:return {'status':'INVALID_OUTPUT','reference_equal':False,'reason':'unfinished_or_nonunique_output'}
    try:
        expected,error=_parse(ref['ground_truth_command'],ref)
        if error:return {'status':'UNKNOWN_REFERENCE','reference_equal':False,'reason':error}
        actual,error=_parse(command,ref)
        if error:return {'status':'UNKNOWN_EQUIVALENCE' if error.endswith('UNSUPPORTED') or error=='UNSUPPORTED_OPTION_SPELLING' else 'MISMATCH','reference_equal':False,'reason':error}
        equal=actual==expected
        return {'status':'MATCH' if equal else 'MISMATCH','reference_equal':equal,'reason':None if equal else 'tool_option_value_or_positional_order_differs'}
    except (ValueError,TypeError,json.JSONDecodeError):return {'status':'UNKNOWN_EQUIVALENCE','reference_equal':False,'reason':'parse_error'}

