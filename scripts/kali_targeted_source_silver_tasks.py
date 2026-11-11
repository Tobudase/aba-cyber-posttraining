"""Training-only Kali command intents grounded in pinned publisher help text.

These are authored examples. They are neither publisher-verified labels nor an
independent evaluation set. Commands are data strings and must not be run.
"""


def recipes():
    return [
        dict(tool="lsblk", family="block-pairs-exclude", query="List block devices in key=value pair format, excluding devices with major number {n}.",
             command="lsblk --pairs --exclude {n}", optional_args={"--pairs|-P": None, "--exclude|-e": "{n}"}, positional_args=[],
             variants=[{"n": "8"}, {"n": "259"}]),
        dict(tool="lsblk", family="block-perms-width", query="Show block device permissions and limit the displayed output width to {n} characters.",
             command="lsblk --perms --width {n}", optional_args={"--perms|-m": None, "--width|-w": "{n}"}, positional_args=[],
             variants=[{"n": "100"}, {"n": "120"}]),
        dict(tool="lsmem", family="memory-pairs-split", query="List memory ranges as key=value pairs, splitting ranges by the {column} column.",
             command="lsmem --pairs --split {column}", optional_args={"--pairs|-P": None, "--split|-S": "{column}"}, positional_args=[],
             variants=[{"column": "STATE"}, {"column": "NODE"}]),
        dict(tool="hardlink", family="hardlink-dryrun-cache", query="Dry-run duplicate-file consolidation in {path}, with cached file-content data limited to {size} bytes; make no file changes.",
             command="hardlink --dry-run --cache-size {size} {path}", optional_args={"--dry-run|-n": None, "--cache-size|-r": "{size}"}, positional_args=["{path}"],
             variants=[{"size": "1048576", "path": "/srv/archive_a"}, {"size": "2097152", "path": "/srv/archive_b"}]),
        dict(tool="hardlink", family="hardlink-dryrun-exclude", query="Dry-run duplicate-file consolidation in {path}, excluding filenames matching regex {pattern}; make no file changes.",
             command="hardlink --dry-run --exclude {pattern} {path}", optional_args={"--dry-run|-n": None, "--exclude|-x": "{pattern}"}, positional_args=["{path}"],
             variants=[{"pattern": "bak$", "path": "/srv/archive_c"}, {"pattern": "tmp$", "path": "/srv/archive_d"}]),
        dict(tool="more", family="more-clean-exit", query="Display {path} without scrolling, cleaning the screen first, then exit at end of file.",
             command="more --clean-print --exit-on-eof {path}", optional_args={"--clean-print|-p": None, "--exit-on-eof|-e": None}, positional_args=["{path}"],
             variants=[{"path": "/var/log/audit/sample_a.log"}, {"path": "/var/log/audit/sample_b.log"}]),
        dict(tool="more", family="more-nopause-exit", query="Display {path}, suppressing pauses after form-feed characters and exiting at end of file.",
             command="more --no-pause --exit-on-eof {path}", optional_args={"--no-pause|-l": None, "--exit-on-eof|-e": None}, positional_args=["{path}"],
             variants=[{"path": "/var/log/audit/sample_c.log"}, {"path": "/var/log/audit/sample_d.log"}]),
        dict(tool="virtualenv", family="venv-clear-prompt", query="Use virtualenv to clear the existing destination {path} before recreating it, with shell prompt {prompt}.",
             command="virtualenv --clear --prompt {prompt} {path}", optional_args={"--clear": None, "--prompt": "{prompt}"}, positional_args=["{path}"],
             variants=[{"path": "/tmp/kali_lab_env_a", "prompt": "lab_a"}, {"path": "/tmp/kali_lab_env_b", "prompt": "lab_b"}]),
    ]
