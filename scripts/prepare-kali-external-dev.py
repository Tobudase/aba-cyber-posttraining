#!/usr/bin/env python3
"""Author a disclosed, narrow doc-checked CLI dev pool; NEVER execute commands."""
from collections import Counter
import json
import shlex

from benchkit import (ROOT, ARTIFACT, artifact_spec, kali_prompts, load_jsonl,
                      row_fingerprint, sha, validate_dataset, verify_isolation,
                      write_json, write_jsonl)


def main():
    source = json.loads((ROOT / 'docs/verification/benchkit-source-preparation.json').read_text())
    docs = {x['path'].rsplit('/', 1)[1][:-5]: x for x in source['files'] if '/docs/' in x['path'] and x['path'].endswith('.html')}
    # Each template family stays in one split. Literal commands are data, no shell calls.
    families = [
        ('checksum-sha256', 'coreutils', 'Calculate the SHA-256 checksum of local evidence file {f}.', 'sha256sum {f}', {}),
        ('checksum-verify', 'coreutils', 'Check the local files against checksum manifest {f}.', 'sha256sum --check {f}', {'--check|-c': None}),
        ('checksum-binary', 'coreutils', 'Calculate SHA-256 of {f} explicitly using binary file mode.', 'sha256sum --binary {f}', {'--binary|-b': None}),
        ('head-five', 'coreutils', 'Show the first five lines of local report {f}.', 'head -n 5 {f}', {'--lines|-n': '5'}),
        ('tail-seven', 'coreutils', 'Show the last seven lines of local report {f}.', 'tail -n 7 {f}', {'--lines|-n': '7'}),
        ('wc-lines', 'coreutils', 'Count newline characters in local report {f}.', 'wc --lines {f}', {'--lines|-l': None}),
        ('dgst-sha256', 'openssl-dgst', 'Use openssl dgst to calculate the SHA-256 digest of local artifact {f}.', 'openssl dgst -sha256 {f}', {'-sha256': None}),
        ('dgst-hex', 'openssl-dgst', 'Use openssl dgst to emit the SHA-256 digest of {f} in hexadecimal.', 'openssl dgst -sha256 -hex {f}', {'-sha256': None, '-hex': None}),
        ('certificate-subject', 'openssl-x509', 'Read PEM certificate {f} and print only its subject, without printing the encoded certificate.', 'openssl x509 -in {f} -noout -subject', {'-in': 'FILE', '-noout': None, '-subject': None}),
        ('certificate-dates', 'openssl-x509', 'Read PEM certificate {f} and print its validity dates, omitting the encoded certificate.', 'openssl x509 -in {f} -noout -dates', {'-in': 'FILE', '-noout': None, '-dates': None}),
        ('certificate-serial', 'openssl-x509', 'Print the serial number of PEM certificate {f}, omitting the encoded certificate.', 'openssl x509 -in {f} -noout -serial', {'-in': 'FILE', '-noout': None, '-serial': None}),
        ('offline-dns', 'tshark', 'Read saved capture {f} with tshark and display only DNS packets; do not capture live traffic.', 'tshark -r {f} -Y dns', {'-r': 'FILE', '-Y': 'dns'}),
        ('offline-tls', 'tshark', 'Read saved capture {f} with tshark and display only TLS packets; do not capture live traffic.', 'tshark -r {f} -Y tls', {'-r': 'FILE', '-Y': 'tls'}),
        ('offline-capture', 'tcpdump', 'Use tcpdump to read packets from saved capture {f} without resolving host addresses; do not capture live traffic.', 'tcpdump -n -r {f}', {'-n': None, '-r': 'FILE'}),
        ('json-event', 'jq', 'Using jq, extract event.type as an unquoted string from JSON file {f}.', "jq -r '.event.type' {f}", {'--raw-output|-r': None}),
        ('json-compact', 'jq', 'Using jq, output each JSON value in {f} in compact form.', "jq -c '.' {f}", {'--compact-output|-c': None}),
        ('log-count', 'grep', 'Count lines containing the literal text FAILED in local log {f} using grep.', "grep -c 'FAILED' {f}", {'--count|-c': None}),
        ('log-line-numbers', 'grep', 'Show lines containing the literal text ERROR in local log {f}, with line numbers, using grep.', "grep -n 'ERROR' {f}", {'--line-number|-n': None}),
    ]
    train = load_jsonl(ARTIFACT / 'kali/KaliBench_data/kalibench_verified_train_3504.jsonl')
    norm = lambda s: ' '.join(shlex.split(s))
    train_cmds = {norm(x['ground_truth_command']) for x in train}
    train_queries = {' '.join(x['query'].lower().split()) for x in train}
    generated, metadata = [], {}
    ordered = sorted(f[0] for f in families)
    # Fixed hash assignment, with no model predictions or test inspection.
    confirm_families = set(sorted(ordered, key=lambda s: sha(('kali-authored-confirm-v1:' + s).encode()))[:6])
    excluded = 0
    for key, doc, query, command, opts in families:
        if doc not in docs:
            raise ValueError('Missing primary documentation ' + doc)
        for ix in range(1, 7):
            ext = 'pem' if key.startswith('certificate') else 'pcap' if key.startswith('offline') else 'json' if key.startswith('json') else 'log' if key.startswith('log') else 'txt'
            f = f'local_evidence_{ix:02d}.{ext}'
            cmd = command.format(f=f)
            q = query.format(f=f)
            if norm(cmd) in train_cmds or ' '.join(q.lower().split()) in train_queries:
                excluded += 1
                continue
            optional = {k: f if v == 'FILE' else v for k, v in opts.items()}
            tokens = shlex.split(cmd)
            flag_values = {a for k, v in optional.items() if v is not None for a in k.split('|')}
            positional = []
            i = 1
            while i < len(tokens):
                if tokens[i] in flag_values:
                    i += 2
                elif tokens[i].startswith('-'):
                    i += 1
                else:
                    positional.append(tokens[i]); i += 1
            identifier = f'authored-doc-v1-{key}-{ix:02d}'
            generated.append({'custom_id': identifier, 'query': q, 'tool_name': tokens[0],
                'ground_truth_command': cmd, 'optional_args': optional, 'positional_args': positional})
            metadata[identifier] = {'group_id': 'authored-family:' + key,
                'split': 'dev_confirm' if key in confirm_families else 'dev_search', 'doc': docs[doc]}
    prompts, labels = kali_prompts(generated)
    pools = {'dev_search': [], 'dev_confirm': []}
    for r in generated:
        identifier = r['custom_id']; m = metadata[identifier]
        row = {'id': identifier, 'benchmark': 'kali', 'task': 'unrestricted',
            'messages': prompts[identifier], 'target': '<output>' + r['ground_truth_command'] + '</output>',
            'native_label': labels[identifier], 'group_id': m['group_id'], 'split': m['split'],
            'training_eligible': False, 'official_test': False, 'self_authored': True,
            'source_url': m['doc']['url'], 'source_sha256': m['doc']['sha256'],
            'quality': 'AUTHORED_DOC_CHECKED_NARROW_SOURCE_SILVER_NOT_EXPERT_GOLD',
            'input_sha256': row_fingerprint(prompts[identifier])}
        pools[m['split']].append(row)
    directory = ROOT / 'data/benchkit/kali-external-dev'
    directory.mkdir(parents=True, exist_ok=True)
    specs = {}
    for split, rows in pools.items():
        validate_dataset(rows, split, 'kali')
        path = directory / f'{split}.jsonl'
        write_jsonl(path, rows)
        specs[split] = artifact_spec(path, rows)
    verify_isolation(pools)
    limitations = ['Self-authored defensive/readonly CLI examples, narrow tool coverage; not representative KaliBench validation.',
                  'Six filename variants per family are correlated, not independent cases; bootstrap by family.',
                  'Dev-confirm families are segregated, but same documentation/tools may occur across development splits.',
                  'Exact command/query overlap checked only against official TRAIN, not official TEST or historical model training.',
                  'No model predictions used to construct or split these rows; no commands executed.',
                  'These development labels require independent audit before strong research claims.']
    manifest = {'schema': 'benchkit.dataset.v1', 'benchmark': 'kali', 'official_test': False,
                'self_authored': True, 'splits': specs, 'limitations': limitations}
    write_json(directory / 'manifest.json', manifest)
    report = {'status': 'NARROW_AUTHORED_DEV_READY_FOR_ENGINEERING',
              'splits': {k: len(v) for k, v in pools.items()}, 'families': len(families),
              'tools': dict(Counter(r['tool_name'] for r in generated)),
              'exact_train_overlaps_excluded': excluded, 'commands_executed': 0,
              'official_test_files_downloaded': 0, 'limitations': limitations}
    write_json(ROOT / 'docs/verification/kali-external-dev-preparation.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
