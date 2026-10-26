"""Standalone package format and integrity checks; no Blender required."""
from pathlib import Path
import hashlib
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from package_skill import build, source_files  # noqa: E402


def test_generated_archives_match(tmp_path):
    zip_file, skill_file, sha = build(tmp_path)
    assert zip_file.read_bytes() == skill_file.read_bytes()
    assert hashlib.sha256(zip_file.read_bytes()).hexdigest() == sha
    with zipfile.ZipFile(zip_file) as bundle:
        names = set(bundle.namelist())
        assert bundle.testzip() is None
        assert 'SKILL.md' in names
        assert 'scripts/run_pipeline.py' in names
        assert 'scripts/file_integrity.py' in names
        assert 'examples/modern_chair.py' in names
        assert not any('__pycache__' in name or name.startswith('tests/') for name in names)
        for file in source_files():
            assert bundle.read(file.relative_to(ROOT).as_posix()) == file.read_bytes()
