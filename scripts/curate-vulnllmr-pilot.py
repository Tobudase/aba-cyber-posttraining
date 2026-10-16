#!/usr/bin/env python3
"""Record agent review and corrected concise evidence, never claim human validation."""
import ast
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import ssl
import ftplib

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'data/trajectories/development_distillation/vulnllmr-reviewed-candidates.jsonl'
    rows = [json.loads(x) for x in source.read_text().splitlines() if x]
    default = ssl.create_default_context()
    assert default.verify_mode == ssl.CERT_REQUIRED and default.check_hostname
    ftp_source = inspect.getsource(ftplib.FTP_TLS.__init__)
    assert 'self.context = context' in ftp_source
    checks, curated = [], []
    for row in rows:
        code = row['messages'][0]['content'].split('\n\n```python\n', 1)[1].rsplit('\n```', 1)[0]
        assert hashlib.sha256(code.encode()).hexdigest() == row['code_sha256']
        tree = ast.parse(code)  # Parse only, never execute dataset snippets.
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        functions = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        sid = row['source_id']
        if sid == '153205':
            assert 'ftp_tls_connection' in functions
            assert any(isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                       and n.func.value.id == 'ssl' and n.func.attr == 'create_default_context' for n in calls)
            assert any(isinstance(n.func, ast.Attribute) and n.func.attr == 'FTP_TLS'
                       and any(k.arg == 'context' and isinstance(k.value, ast.Name) and k.value.id == 'context'
                               for k in n.keywords) for n in calls)
            explanation = ('The function explicitly passes ssl.create_default_context() to FTP_TLS, enabling '
                           'certificate-chain and hostname verification under the checked Python 3.12 defaults. '
                           'The snippet does not disable those checks, so this review finds no CWE-295 issue.')
            evidence = 'AST: default context explicitly passed to FTP_TLS; local stdlib: CERT_REQUIRED and check_hostname=True.'
            modification = 'Narrowed claim to checked Python version and CWE scope.'
        elif sid in {'151523', '151522'}:
            assert 'upload_user_file' in functions
            loops = [n for n in ast.walk(tree) if isinstance(n, ast.While)]
            assert len(loops) == 1
            assert any(isinstance(n, ast.Break) for n in ast.walk(loops[0]))
            comparisons = [n for n in ast.walk(tree) if isinstance(n, ast.Compare)]
            bounded = any(isinstance(n.left, ast.Name) and n.left.id == 'total_size'
                          and any(isinstance(x, ast.Name) and x.id == 'MAX_FILE_SIZE' for x in n.comparators)
                          and any(isinstance(x, ast.Gt) for x in n.ops) for n in comparisons)
            if sid == '151523':
                assert bounded and row['source_target'] == 0
                explanation = ('The function adds each chunk length to total_size and raises before writing a chunk '
                               'that would exceed the 50 MiB limit. This bounds writes for one call; it does not '
                               'establish quotas across concurrent uploads or bound a blocking input stream.')
                evidence = 'AST: cumulative size comparison against MAX_FILE_SIZE and raise before output_file.write.'
                modification = 'Limited negative claim to one-call file-size control; no blanket resource-safety claim.'
            else:
                assert not bounded and row['source_target'] == 1
                explanation = ('The loop stops at end-of-input but has no check on cumulative bytes written. '
                               'If untrusted upload size is not limited elsewhere, a large input can consume '
                               'unbounded storage relative to this function, consistent with CWE-400.')
                evidence = 'AST: EOF break present; no cumulative size comparison. Application-level limits remain unknown.'
                modification = 'Corrected false infinite-loop wording and stated the missing external-quota assumption.'
        else:
            raise ValueError('New candidate needs an explicit evidence review; refusing automatic approval')
        output = explanation + '\n\n## Final Answer\n#judge: ' + ('yes' if row['source_target'] else 'no') + '\n#type: ' + (row['source_cwes'][0] if row['source_target'] else 'N/A')
        result = dict(row)
        result['messages'] = [row['messages'][0], {'role': 'assistant', 'content': output}]
        result.update({'role': 'agent_reviewed_development_candidate', 'reviewer': 'Codex agent, not independent human',
                       'agent_review_complete': True, 'independent_explanation_review_complete': False,
                       'training_eligible': False, 'review_evidence': evidence})
        curated.append(result)
        checks.append({'source_id': sid, 'code_sha256': row['code_sha256'], 'evidence': evidence,
                       'revision': modification, 'agent_review_complete': True, 'human_review_complete': False})
    dest = source.with_name('vulnllmr-agent-reviewed-pilot.jsonl')
    dest.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in curated))
    report = {'reviewed_at': datetime.now(timezone.utc).isoformat(), 'records': len(curated),
              'source_candidates_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'curated_sha256': hashlib.sha256(dest.read_bytes()).hexdigest(), 'checks': checks,
              'snippets_executed': False, 'network_connections_opened': False, 'training_executed': False,
              'training_ready_records': 0, 'human_review_complete': False, 'formal_split_frozen': False,
              'python_ssl_reference': 'https://docs.python.org/3.12/library/ssl.html#ssl.create_default_context',
              'stdlib_ftp_reference': 'https://github.com/python/cpython/blob/3.12/Lib/ftplib.py'}
    (ROOT / 'docs/verification/vulnllmr-agent-content-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'agent_reviewed_records': len(curated), 'training_ready_records': 0,
                      'source_snippets_executed': False, 'output': str(dest)}, indent=2))


if __name__ == '__main__':
    main()
