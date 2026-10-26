"""Offline checks and optional live Blender smoke test (pytest -q)."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "scripts" / "run_pipeline.py"
SAMPLE = ROOT / "examples" / "modern_chair.py"


def make_fake_blender(folder: Path, *, qa_errors=False, fail_build=False, skip_preview=False, bad_export=False, skip_export=False, bad_qa=False):
    """Protocol fake: validate orchestration without claiming Blender was tested."""
    path = folder / "fake_blender.py"
    path.write_text('''#!/usr/bin/env python3
import json, pathlib, struct, sys, zlib
args = sys.argv[1:]
assert '--python-exit-code' in args
assert '--python' in args
script = pathlib.Path(args[args.index('--python')+1]).name
assert '--' in args
flags = args[args.index('--')+1:]
def value(flag): return flags[flags.index(flag)+1]
def chunk(tag, data):
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data))
def png(size):
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    pixels = b''.join(b'\\x00' + b'\\x70\\x80\\x90' * size for _ in range(size))
    return b'\\x89PNG\\r\\n\\x1a\\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')
if script == 'modern_chair.py':
    if %r: sys.exit(17)
    pathlib.Path(value('--output')).write_bytes(b'BLENDER-v300dummy-content')
elif script == 'qa_blender.py':
    report = {'profile': value('--profile'), 'errors': ['bad mesh'] if %r else [], 'warnings': [], 'total_triangles': 42}
    if %r: report['total_triangles'] = 'invalid'
    pathlib.Path(value('--report')).write_text(json.dumps(report))
elif script == 'render_preview.py':
    if not %r:
        for view in ('hero','front','side'):
            (pathlib.Path(value('--outdir')) / ('preview_'+view+'.png')).write_bytes(png(int(value('--resolution'))))
elif script == 'export_asset.py':
    if not %r:
        path = pathlib.Path(value('--output'))
        if %r:
            path.write_bytes(b'invalid export dummy')
        elif value('--format') == 'glb':
            payload = json.dumps({'asset': {'version': '2.0'}, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}], 'meshes': [{'primitives': [{'attributes': {}}]}]}).encode()
            payload += b' ' * (-len(payload) %% 4)
            path.write_bytes(b'glTF' + struct.pack('<II', 2, 20+len(payload)) + struct.pack('<I4s', len(payload), b'JSON') + payload)
        else: path.write_bytes(b'Kaydara FBX Binary  \\x00\\x1a\\x00' + b'0' * 64)
else: sys.exit(19)
''' % (fail_build, qa_errors, bad_qa, skip_preview, skip_export, bad_export))
    path.chmod(0o755)
    return path


def run(tmp_path, blender, *extra):
    return subprocess.run([sys.executable, str(PIPELINE), '--blender', str(blender),
            '--script', str(SAMPLE), '--outdir', str(tmp_path/'output'),
            '--name', 'chair', '--resolution', '256', *extra],
            capture_output=True, text=True)


def test_normal_path_and_file_integrity(tmp_path):
    fake = make_fake_blender(tmp_path)
    result = run(tmp_path, fake, '--formats', 'glb', 'fbx')
    assert result.returncode == 0, result.stderr
    target = tmp_path/'output'
    for name in ['chair.blend', 'chair.glb', 'chair.fbx', 'qa.json',
                 'preview_hero.png', 'preview_front.png', 'preview_side.png',
                 'pipeline_summary.json']:
        assert (target/name).stat().st_size > 0
    assert json.loads((target/'pipeline_summary.json').read_text())['quality_status'] == 'AUTOMATED_QA_PASSED'
    assert run(tmp_path, fake).returncode != 0, 'must not silently overwrite'
    assert run(tmp_path, fake, '--overwrite').returncode == 0


def test_quality_gate_prevents_export(tmp_path):
    fake = make_fake_blender(tmp_path, qa_errors=True)
    result = run(tmp_path, fake)
    assert result.returncode == 2
    assert not (tmp_path/'output'/'chair.glb').exists()
    assert run(tmp_path, fake, '--allow-qa-errors', '--overwrite').returncode == 0
    summary = json.loads((tmp_path/'output'/'pipeline_summary.json').read_text())
    assert summary['quality_status'] == 'DRAFT_HAS_QA_ERRORS'


def test_blender_python_failure_fails_build(tmp_path):
    fake = make_fake_blender(tmp_path, fail_build=True)
    result = run(tmp_path, fake)
    assert result.returncode == 2
    assert 'build failed' in result.stderr
    assert not (tmp_path/'output'/'chair.glb').exists()


def test_missing_preview_fails(tmp_path):
    fake = make_fake_blender(tmp_path, skip_preview=True)
    result = run(tmp_path, fake)
    assert result.returncode == 2
    assert 'Missing output' in result.stderr
    assert not (tmp_path/'output'/'chair.glb').exists()


def test_invalid_config_does_not_start(tmp_path):
    fake = make_fake_blender(tmp_path)
    assert run(tmp_path, fake, '--resolution', '32').returncode != 0
    assert run(tmp_path, fake, '--max-triangles', '-1').returncode != 0
    assert run(tmp_path, fake, '--samples', '999').returncode != 0


@pytest.mark.skipif(not shutil.which('blender'), reason='Blender not installed')
def test_live_blender_sample(tmp_path):
    result = run(tmp_path, shutil.which('blender'), '--profile', 'render', '--samples', '8')
    assert result.returncode == 0, result.stderr + result.stdout
    qa = json.loads((tmp_path/'output'/'qa.json').read_text())
    assert qa['total_triangles'] > 0
    assert not qa['errors']


def test_bad_qa_report_is_rejected(tmp_path):
    fake = make_fake_blender(tmp_path, bad_qa=True)
    result = run(tmp_path, fake)
    assert result.returncode == 2
    assert 'invalid or mismatched schema' in result.stderr
    assert not (tmp_path/'output'/'chair.glb').exists()


def test_export_integrity_checked(tmp_path):
    fake = make_fake_blender(tmp_path, bad_export=True)
    result = run(tmp_path, fake)
    assert result.returncode == 2
    assert 'Not a binary GLB' in result.stderr
    assert not (tmp_path/'output'/'pipeline_summary.json').exists()


def test_overwrite_cannot_reuse_stale_export(tmp_path):
    fake = make_fake_blender(tmp_path)
    assert run(tmp_path, fake).returncode == 0
    missing_export = make_fake_blender(tmp_path, skip_export=True)
    result = run(tmp_path, missing_export, '--overwrite')
    assert result.returncode == 2
    assert 'Missing output' in result.stderr
    assert not (tmp_path/'output'/'chair.glb').exists()
    assert not (tmp_path/'output'/'pipeline_summary.json').exists()
