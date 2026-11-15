"""Versioned util-linux 2.37.2 preview oracle, independent of candidate flags.

The actual dry-run must report the intended aggregate links without mutation.
A second disposable fixture executes the SAME argv with only -n/--dry-run
removed, to verify the proposed partition. This is an evaluator shadow run,
not model execution success, and never repairs other options or paths.
"""
import hashlib
import re
import stat
import os
import subprocess
import tempfile
from pathlib import Path


def snapshot(root):
    result = {}
    for path in Path(root).rglob('*'):
        if path.is_file() and not path.is_symlink():
            s = path.stat()
            result[str(path.relative_to(root))] = {
                'inode': s.st_ino, 'links': s.st_nlink,
                'mode': stat.S_IMODE(s.st_mode), 'mtime_ns': s.st_mtime_ns,
                'uid': s.st_uid, 'gid': s.st_gid, 'size': s.st_size,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return result


def expected_groups(before, directory):
    groups = {}
    for name, item in before.items():
        if not name.startswith(directory.rstrip('/') + '/'):
            continue
        key = tuple(item[k] for k in ['sha256', 'size', 'mode', 'mtime_ns', 'uid', 'gid'])
        groups.setdefault(key, []).append(name)
    return list(groups.values())


def preview_ok(before, after, stdout, directory, returncode=0):
    if returncode != 0 or before != after:
        return False
    text = stdout.decode(errors='replace') if isinstance(stdout, bytes) else stdout
    mode = re.findall(r'^Mode:\s+(\S+)\s*$', text, re.M)
    linked = re.findall(r'^Linked:\s+(\d+) files\s*$', text, re.M)
    expected = sum(len(g) - 1 for g in expected_groups(before, directory))
    # These fixtures deliberately contain duplicates: accepting an empty preview
    # would repeat the original vacuous-success bug.
    return expected > 0 and mode == ['dry-run'] and linked == [str(expected)]


def shadow_argv(argv):
    if not argv or argv[0] != 'hardlink':
        raise ValueError('Only reviewed hardlink argv are eligible')
    if not any(x in ['-n', '--dry-run'] for x in argv[1:]):
        raise ValueError('No explicit dry-run flag: do not transform a command')
    return [argv[0]] + [x for x in argv[1:] if x not in ['-n', '--dry-run']]


def partition_ok(before, after, directory):
    names = sorted(n for n in before if n.startswith(directory.rstrip('/') + '/'))
    if set(before) != set(after) or not names:
        return False
    groups = expected_groups(before, directory)
    expected = {n: i for i, group in enumerate(groups) for n in group}
    if any(before[n]['sha256'] != after[n]['sha256'] for n in before):
        return False
    return all((after[a]['inode'] == after[b]['inode']) == (expected[a] == expected[b])
               for i, a in enumerate(names) for b in names[i + 1:])


def execute_preview(argv, materialize, directory):
    """Execute an admitted argv twice in separate fixtures; never use a shell."""
    env = dict(os.environ, LC_ALL='C', LANG='C')
    try:
        with tempfile.TemporaryDirectory(prefix='kali-preview-actual-') as temp:
            root = Path(temp)
            materialize(root)
            before = snapshot(root)
            result = subprocess.run(argv, cwd=root, env=env, capture_output=True, timeout=15)
            if not preview_ok(before, snapshot(root), result.stdout, directory, result.returncode):
                return False
        with tempfile.TemporaryDirectory(prefix='kali-preview-shadow-') as temp:
            root = Path(temp)
            materialize(root)
            before = snapshot(root)
            result = subprocess.run(shadow_argv(argv), cwd=root, env=env, capture_output=True, timeout=15)
            return result.returncode == 0 and partition_ok(before, snapshot(root), directory)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False
