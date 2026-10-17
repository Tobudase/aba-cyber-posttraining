#!/usr/bin/env python3
"""Author simple non-benchmark weakness descriptions for integration checks.

No real CVE/GHSA identifiers, code, payloads, exploits or official test rows.
Gold labels reflect the single mechanism explicitly described; these easy,
synthetic examples cannot measure real-world CTI capability or generalization.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('CWE-89', 'An application builds a database query by joining raw user text with SQL syntax, without parameterization. The input can change the query structure.', 'A search service treats untrusted form text as part of an SQL statement instead of binding it as data.'),
    ('CWE-79', 'A web application places untrusted comment text in an HTML page without context-appropriate escaping. The browser interprets the text as active page content.', 'A comment renderer returns attacker-controlled content as executable HTML in another user\'s browser rather than encoding the content as text.'),
    ('CWE-78', 'A service joins an untrusted request field to a shell command and executes the resulting command string, allowing the input to alter shell syntax.', 'A maintenance feature embeds external text in a command interpreted by the operating-system shell without separating data from command syntax.'),
    ('CWE-22', 'A file service accepts a relative path from a client and joins it with an intended document root, but fails to confine the resolved path to that root.', 'A download feature lets client-supplied parent-directory components escape the designated storage directory.'),
    ('CWE-918', 'A server fetches a URL supplied by an external client without restricting destinations. It can be directed to resources reachable only from the server.', 'An image proxy follows an untrusted destination address and makes server-side requests to internal services without an allowlist.'),
    ('CWE-352', 'A state-changing web request relies on ambient session cookies and has no anti-forgery token or origin verification. A different site can induce the authenticated browser to send it.', 'A browser automatically attaches the victim\'s login cookies to a sensitive action initiated by an unrelated web page, and the application does not check that the user intended that action.'),
    ('CWE-787', 'A native parser copies an externally specified number of bytes into a fixed-size heap allocation without checking the destination capacity, writing beyond its end.', 'An array update accepts an index above the allocated upper bound and stores a value outside the buffer.'),
    ('CWE-125', 'A parser uses a client-controlled index to read an array element without checking the upper bound. The read can access memory after the allocation.', 'A message reader trusts an advertised length and reads past the end of the available buffer, potentially disclosing adjacent memory.'),
    ('CWE-416', 'A program frees a heap object but retains an alias, and a later operation dereferences that alias after the allocation has been released.', 'A callback accesses an object through a dangling pointer after another component has already deallocated the same object.'),
    ('CWE-415', 'Two cleanup paths independently release the same heap allocation, so the allocator is asked to free the identical allocation twice.', 'Error handling deallocates an object that an earlier cleanup branch already freed, without resetting ownership.'),
    ('CWE-476', 'A program does not check whether an allocation or lookup returned a null pointer and dereferences that pointer.', 'A service accesses a field through a pointer that may be null after a failed object lookup.'),
    ('CWE-190', 'An unsigned integer multiplication used to compute an allocation size wraps around the maximum representable value. The arithmetic result is smaller than intended.', 'A size counter overflows its fixed-width integer range during addition, producing a wrapped value before any buffer operation.'),
    ('CWE-369', 'A numeric service divides by a client-supplied value without rejecting zero, causing a division-by-zero fault.', 'A calculation uses an unchecked external denominator that can equal zero and terminates with an arithmetic fault.'),
    ('CWE-611', 'An XML parser processes external entity declarations in untrusted documents and resolves the referenced resources without disabling external entity expansion.', 'A document import enables XML external entities for untrusted input, allowing the parser to retrieve unintended local or remote resources.'),
    ('CWE-502', 'A service deserializes an untrusted object graph using a native object deserializer that can instantiate attacker-chosen classes and trigger side effects.', 'An application restores serialized objects from untrusted input without restricting the types or behavior executed during deserialization.'),
    ('CWE-295', 'A TLS client encrypts its connection but accepts any peer certificate without validating its trust chain or expected identity.', 'A network client disables server-certificate validation and therefore cannot authenticate the encrypted connection\'s peer.'),
    ('CWE-798', 'A service contains a fixed administrative password in its source code. Every deployed instance accepts the same embedded credential.', 'An application embeds a reusable secret credential directly in its compiled program rather than obtaining a deployment-specific credential.'),
    ('CWE-256', 'An application stores user passwords as readable plaintext in its credential database rather than using an appropriate password-hashing scheme.', 'A configuration file records login passwords verbatim, so anyone reading the file can recover the original passwords directly.'),
    ('CWE-327', 'An application deliberately uses a cryptographic algorithm known to be broken for confidentiality, despite requiring modern encryption strength.', 'Sensitive data is encrypted using an obsolete, insecure cipher whose cryptographic design is no longer considered secure.'),
    ('CWE-338', 'An application generates security tokens with a general-purpose pseudorandom generator that is unsuitable for cryptographic use.', 'Password-reset tokens are produced using a predictable non-cryptographic random-number generator rather than a cryptographically secure source.'),
    ('CWE-306', 'An administrative endpoint performs a critical privileged operation without requiring any caller authentication.', 'A critical management function is directly callable by unauthenticated clients because no identity check is performed.'),
    ('CWE-862', 'An authenticated user can access another account\'s private object because the application performs no authorization check for object ownership.', 'A service verifies that a caller is logged in but never checks whether that caller has permission to perform the requested operation.'),
    ('CWE-209', 'An application returns detailed internal stack traces, database connection information and private filesystem paths in externally visible error responses.', 'A public error page includes sensitive implementation details and secrets from an exception rather than returning a sanitized failure message.'),
    ('CWE-367', 'A program checks a file\'s security properties, then opens it later using its path. Another process can replace the file between the check and use.', 'A security-sensitive file operation trusts the result of an earlier path check even though the underlying filesystem object can change before the operation uses it.'),
]

directory = ROOT/'data/synthetic/cti-rcm-fixture'
directory.mkdir(parents=True, exist_ok=True)
rows = []
for index, (label, short, paraphrase) in enumerate(CASES):
    for variant, text in [('a', short), ('b', paraphrase)]:
        rows.append({'id': f'synthetic-{index+1:02d}-{variant}',
                     'group': f'synthetic-{index+1:02d}', 'description': text,
                     'label': label, 'synthetic_only': True,
                     'purpose': 'ENGINEERING_FORMAT_AND_THROUGHPUT_ONLY',
                     'training_eligible': False, 'official_benchmark_record': False})
data = ''.join(json.dumps(row)+'\n' for row in rows)
(directory/'examples.jsonl').write_text(data)
manifest = {'status': 'ENGINEERING_ONLY_NOT_RESEARCH_TRAINING_OR_TEST',
            'origin': 'New descriptions authored in this project; no official benchmark rows',
            'records': len(rows), 'mechanisms': len(CASES),
            'paraphrase_groups': len(CASES), 'gold_labels_manually_reviewed': True,
            'independent_expert_gold_validation': False,
            'real_vulnerability_identifiers': 0, 'official_test_rows': 0,
            'examples_sha256': hashlib.sha256(data.encode()).hexdigest(),
            'limitation': 'Simple authored mechanisms, paired paraphrases and non-independent gold labels; no benchmark/generalization claim.'}
(directory/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
(directory/'README.md').write_text('''# CTI-RCM integration fixture

48 newly authored weakness descriptions, two paraphrases for each of 24
mechanisms. No real CVE/GHSA identifiers, executable code, payloads or official
test records. Intended for parser/template and rough local throughput checks.
Gold labels were reviewed by the authoring assistant, not independent experts.
The paired descriptions are not independent samples and are not a research
train/dev/test split. Do not use their accuracy as real-world performance.
All records remain training_eligible=false. Never mix this fixture into an
official benchmark or report its score as CTI-Bench accuracy.
''')
print(json.dumps(manifest, indent=2))
