#!/usr/bin/env python3
"""Check pinned source patch and native action argument validation, no model call."""
import argparse,hashlib,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--aba-root',type=Path,required=True);a=p.parse_args()
source=a.aba_root/'engine/builtin/nb_tree/search.py'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='3b1cf04008fc0ee01ee4329fc90a527cbdf5326196497b5dd1c007d6695628d6'
sys.path.insert(0,str(a.aba_root.resolve()))
from aibuildai_version import preload_source_runtime
preload_source_runtime()
from engine.builtin.nb_tree.candidate import CompleteWorker
from engine.durable_execution import _encoded_request,_NO_REQUEST
assert _encoded_request(CompleteWorker,'run',_NO_REQUEST) is None
try:_encoded_request(CompleteWorker,'run','Start the assigned work.')
except TypeError:pass
else:raise AssertionError('The native no-request contract was weakened')
print(json.dumps({'status':'ACTION_REQUEST_CONTRACT_PASS','patch_source_hash_matched':True,'invalid_request_rejected':True,'model_calls':0}))
