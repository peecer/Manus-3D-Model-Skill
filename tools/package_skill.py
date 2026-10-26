#!/usr/bin/env python3
"""Reproducibly package a Manus skill (ZIP and .skill share the exact bytes)."""
from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = 'precision-3d-modeler'
REQUIRED = ('SKILL.md', 'README.md', 'LICENSE.txt')
SOURCE_DIRS = ('scripts', 'examples', 'references')


def source_files() -> list[Path]:
    paths = [ROOT / relative for relative in REQUIRED]
    for directory in SOURCE_DIRS:
        paths.extend(path for path in (ROOT / directory).rglob('*')
                     if path.is_file() and path.suffix in {'.py', '.md'})
    if not all(path.is_file() for path in paths):
        raise ValueError('Required package files are missing')
    if any(path.is_symlink() for path in paths):
        raise ValueError('Symlinks are disallowed in portable skill packages')
    skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
    if not re.match(r'^---\s*\nname: precision-3d-modeler\s*\ndescription: .+\n', skill):
        raise ValueError('SKILL.md must start with supported YAML name/description metadata')
    return sorted(paths, key=lambda path: path.relative_to(ROOT).as_posix())


def build(output_dir: Path) -> tuple[Path, Path, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = source_files()
    zippath = output_dir / (NAME + '.zip')
    with zipfile.ZipFile(zippath, 'w') as archive:
        for file in files:
            rel = file.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(rel, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, file.read_bytes())
    with zipfile.ZipFile(zippath) as archive:
        if archive.testzip() or set(archive.namelist()) != {f.relative_to(ROOT).as_posix() for f in files}:
            raise RuntimeError('Skill archive verification failed')
    data = zippath.read_bytes()
    skillpath = output_dir / (NAME + '.skill')
    skillpath.write_bytes(data)
    return zippath, skillpath, hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    zip_path, skill_path, digest = build(args.output_dir)
    print('ZIP:', zip_path)
    print('SKILL:', skill_path)
    print('SHA256 (both):', digest)


if __name__ == '__main__':
    main()
