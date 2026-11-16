"""Offline arithmetic and evidence hash verification; no model execution."""
from pathlib import Path
import json,hashlib
p=Path(__file__).resolve().parents[1]/'results/kali-mode-repair-2026-11-16'
s=json.loads((p/'summary.json').read_text())
for n,h in s['evidence_sha256'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h,n
fit=json.loads((p/'final-greedy-TRAIN384-diagnostic-analysis.json').read_text())['candidates']
modes=json.loads((p/'PyI-mode-collapse-and-teacher-advantage-audit.json').read_text())['new_PyI64_modes']
for arm in ['R','RK']:
 a=fit[arm+'_step192'];f=a['full_TRAIN'];assert sum(f['counts'].values())==384
 assert f['lower']==f['counts']['fixture_pass']==s[arm]['TRAIN_PASS']
 assert f['upper']==f['lower']+sum(v for k,v in f['counts'].items() if k.startswith('unknown'))
 assert sum(v['lower'] for v in a['per_tool'].values())==f['lower']
 assert sum(v[arm+'_PASS'] for v in modes.values())==a['subgroups']['new_PyI64']['PASS_lower']
 assert a['per_tool']['hardlink']['lower']==128 and not a['full_TRAIN_at_least360']
assert sum(v['rows'] for v in modes.values())==64
assert s['fresh_v9_confirmation_queries']==s['official_TEST_queries']==0
print('PASS: saved evidence hashes, denominators, per-tool/mode totals, unresolved bounds. No full model reproduction claim.')
