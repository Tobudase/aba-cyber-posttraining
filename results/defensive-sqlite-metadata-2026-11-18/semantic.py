"""Secondary format-independent measure. Accept one complete, unambiguous numeric answer."""
import json,re
from teacher import answer
def semantic(text):
    if '<answer>' in text:return answer(text)
    s=text.strip()
    fenced=re.fullmatch(r'```(?:json)?\s*(\{.*\})\s*```',s,re.S|re.I)
    if fenced:s=fenced[1]
    try:d=json.loads(s)
    except ValueError:return None
    if isinstance(d,dict) and set(d)=={'offset','width','value'} and all(type(v)==int for v in d.values()):return d
    return None
