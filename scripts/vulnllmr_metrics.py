"""Strict development metrics. These are not the upstream paper's scorer."""
import re


def parse_answer(text):
    tail = text.rsplit('## Final Answer', 1)[-1]
    judges = re.findall(r'^\s*#judge:\s*(yes|no)\s*$', tail, re.I | re.M)
    types = re.findall(r'^\s*#type:\s*(CWE-\d+|N/A)\s*$', tail, re.I | re.M)
    if len(judges) != 1 or len(types) != 1:
        return {'valid': False, 'judge': None, 'cwe': None}
    judge, cwe = judges[0].lower(), types[0].upper()
    valid = (judge == 'yes' and cwe != 'N/A') or (judge == 'no' and cwe == 'N/A')
    return {'valid': valid, 'judge': judge if valid else None, 'cwe': cwe if valid else None}


def score(rows):
    counts = {k: 0 for k in ['tp', 'fp', 'fn', 'tn', 'invalid', 'typed_exact']}
    for row in rows:
        pred = parse_answer(row['output'])
        gold = bool(row['target'])
        if not pred['valid']:
            counts['invalid'] += 1
            continue
        positive = pred['judge'] == 'yes'
        counts[('tp' if positive else 'fn') if gold else ('fp' if positive else 'tn')] += 1
        if positive == gold and (not gold or pred['cwe'] in row['gold_cwes']):
            counts['typed_exact'] += 1
    valid = len(rows) - counts['invalid']
    def ratio(a, b):
        return a / b if b else None
    return {**counts, 'total': len(rows), 'valid_outputs': valid,
            'format_valid_rate': ratio(valid, len(rows)),
            'binary_accuracy_all_invalid_incorrect': ratio(counts['tp'] + counts['tn'], len(rows)),
            'typed_exact_accuracy_all_invalid_incorrect': ratio(counts['typed_exact'], len(rows)),
            'binary_f1_valid_outputs_only': ratio(2 * counts['tp'], 2 * counts['tp'] + counts['fp'] + counts['fn']),
            'scope': 'development smoke only; invalid outputs excluded from confusion matrix and never counted correct'}
