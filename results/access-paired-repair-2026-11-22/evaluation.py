"""Separate a completed, strictly formatted answer from a recoverable terminal answer."""
import re

OUTPUT = re.compile(r'<output>\s*([^<>\r\n]+?)\s*</output>')
def parse_completion(text, ended):
    if not ended:
        return dict(format_ok=False, command='', issue='length_limit')
    _,closed,final=text.rpartition('</think>')
    if closed:
        match=OUTPUT.fullmatch(final.strip())
        if match and match[1].strip():
            return dict(format_ok=True,command=match[1].strip(),issue=None)
        return dict(format_ok=False,command='',issue='malformed_final')
    if text.count('<output>')==text.count('</output>')==1:
        match=OUTPUT.search(text)
        if match and match[1].strip() and not text[match.end():].strip():
            return dict(format_ok=False,command=match[1].strip(),issue='missing_think_close')
    return dict(format_ok=False,command='',issue='no_unique_terminal_answer')
