#!/usr/bin/env python3
"""List NRP models without exposing credentials or making generation calls."""
import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import ssl
import stat
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
KEY_FILE = ROOT / '.secrets/nrp_api_key'
BASE_URL = 'https://ellm.nrp-nautilus.io/v1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save-key', action='store_true', help='Prompt privately in a local terminal and save with mode 600')
    args = parser.parse_args()
    if args.save_key:
        if not sys.stdin.isatty():
            parser.error('--save-key requires an interactive local terminal')
        token = getpass.getpass('NRP LLM token (hidden; do not paste in chat): ').strip()
        if not token or any(c.isspace() for c in token):
            parser.error('Token is empty or contains whitespace')
        KEY_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if KEY_FILE.is_symlink():
            parser.error('Refusing a symlink credential file')
        fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as out:
            os.fchmod(out.fileno(), 0o600)
            out.write(token + '\n')
    token = os.environ.get('NRP_API_KEY', '').strip()
    if not token and KEY_FILE.is_file():
        if stat.S_IMODE(KEY_FILE.stat().st_mode) & 0o077:
            parser.error('Credential file must be private: chmod 600 .secrets/nrp_api_key')
        token = KEY_FILE.read_text().strip()
    if not token:
        print('No NRP LLM token configured. Create one at https://nrp.ai/llmtoken/ then run this script with --save-key in a local terminal.')
        return 2
    request = urllib.request.Request(BASE_URL + '/models', headers={'Authorization': 'Bearer ' + token})
    try:
        # No redirects: never forward a credential to a different host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        context = ssl.create_default_context()
        if sys.platform == 'darwin' and ssl.get_default_verify_paths().cafile is None:
            system_ca = Path('/etc/ssl/cert.pem')
            if system_ca.is_file():
                context.load_verify_locations(cafile=str(system_ca))
        opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=context))
        with opener.open(request, timeout=30) as response:
            body = response.read(2 * 1024 * 1024)
        payload = json.loads(body)
        models = sorted(item['id'] for item in payload.get('data', []) if isinstance(item, dict) and 'id' in item)
    except urllib.error.HTTPError as exc:
        print(f'NRP /models returned HTTP {exc.code}; verify token validity and group LLM flag. Response body omitted.')
        return 1
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
        print('NRP model check failed due to network or response format. No credential was printed.')
        return 1
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'endpoint': BASE_URL,
              'models': models, 'generation_called': False}
    dest = ROOT / 'docs/verification/nrp-model-access.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
