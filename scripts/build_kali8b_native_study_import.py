"""Import the date-independent native task builder without executing its CLI."""
import importlib.util
from pathlib import Path
_s=importlib.util.spec_from_file_location('_kali8b_task',Path(__file__).with_name('build-kali8b-native-study.py'))
_m=importlib.util.module_from_spec(_s);_s.loader.exec_module(_m)
build_task=_m.build
