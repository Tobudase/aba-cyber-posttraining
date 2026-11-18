set -e
sudo dnf install -y -q git gcc make bison flex perl libuuid-devel zlib-devel readline-devel python3.12 python3.12-devel bubblewrap >/tmp/aba-prereqs.log 2>&1
sudo mkfs.ext4 -q /dev/vdc
sudo mkdir -p /mnt/aba-scratch
sudo mount /dev/vdc /mnt/aba-scratch
sudo chown fedora /mnt/aba-scratch
mkdir -p /mnt/aba-scratch/cache /mnt/aba-scratch/local
[ ! -e /home/fedora/.cache ] && ln -s /mnt/aba-scratch/cache /home/fedora/.cache
[ ! -e /home/fedora/.local ] && ln -s /mnt/aba-scratch/local /home/fedora/.local
curl -fsSL -o /tmp/miniforge.sh https://github.com/conda-forge/miniforge/releases/download/24.11.3-0/Miniforge3-24.11.3-0-Linux-x86_64.sh
curl -fsSL -o /tmp/miniforge.sha256 https://github.com/conda-forge/miniforge/releases/download/24.11.3-0/Miniforge3-24.11.3-0-Linux-x86_64.sh.sha256
python3 -c "import hashlib,pathlib;assert hashlib.sha256(pathlib.Path('/tmp/miniforge.sh').read_bytes()).hexdigest()==pathlib.Path('/tmp/miniforge.sha256').read_text().split()[0]"
bash /tmp/miniforge.sh -b -p /mnt/aba-scratch/conda >/tmp/miniforge-install.log 2>&1
/mnt/aba-scratch/conda/bin/conda create -q -y -n manager python=3.12 pip >/tmp/conda-manager.log 2>&1
git clone -q https://github.com/aibuildai-inc/aibuildai-llm-posttrain-agent.git /mnt/aba-scratch/aba
cd /mnt/aba-scratch/aba
git checkout -q c8bd734cafd5a7cd609efb5f561594bde4107d5b
python3 - <<'PATCH'
import hashlib,json,pathlib
p=pathlib.Path('engine/builtin/nb_tree/search.py');s=p.read_text();old=' '*24+'candidate.run,'+chr(10)+' '*24+'"Start the assigned work.",'+chr(10);new=' '*24+'candidate.run,'+chr(10);assert s.count(old)==1
p.write_text(s.replace(old,new));pathlib.Path('/mnt/aba-scratch/compat-patch.json').write_text(json.dumps({'file':str(p),'before_sha256':hashlib.sha256(s.encode()).hexdigest(),'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'change':'Remove business request from zero-request Composite action call; no guards changed.'}))
PATCH
/mnt/aba-scratch/conda/envs/manager/bin/python -m pip install -q -r requirements.lock >/tmp/aba-pip.log 2>&1
/mnt/aba-scratch/conda/envs/manager/bin/python -m pip install -q -e . --no-deps
/mnt/aba-scratch/conda/envs/manager/bin/aibuildai setup >/tmp/aba-setup.log 2>&1
/mnt/aba-scratch/conda/envs/manager/bin/python -c "from infra.process.conda_env import conda_root;assert conda_root()=='/mnt/aba-scratch/conda';print('REAL_CONDA_RUNTIME_OK')"
/mnt/aba-scratch/conda/envs/manager/bin/python - <<'TEST'
from aibuildai_version import preload_source_runtime
preload_source_runtime()
from engine.builtin.nb_tree.candidate import CompleteWorker
from engine.durable_execution import _encoded_request,_NO_REQUEST
assert _encoded_request(CompleteWorker,'run',_NO_REQUEST) is None
try:_encoded_request(CompleteWorker,'run','Start the assigned work.')
except TypeError:pass
else:raise AssertionError('Unexpected action request contract')
print('ACTION_REQUEST_CONTRACT_TEST_PASS')
TEST
bwrap --ro-bind / / --dev-bind /dev /dev --proc /proc /bin/true
