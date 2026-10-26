#!/usr/bin/env python3
"""Run a Blender build -> QA -> preview -> export pipeline with durable logs.

Requires an external Blender executable. Does not fetch code or assets.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from file_integrity import InvalidOutput, validate_file

HERE = Path(__file__).resolve().parent


def run_step(blender: str, label: str, args: list[str], outdir: Path) -> None:
    print(f"[{label}] starting", flush=True)
    command = [blender, "--background", "--threads", "2", "--python-exit-code", "17", *args]
    proc = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, cwd=str(outdir), errors="replace")
    log_path = outdir / "logs" / (label + ".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("COMMAND: " + repr(command) + "\n\n" + proc.stdout, encoding="utf-8")
    if proc.returncode:
        tail = "\n".join(proc.stdout.splitlines()[-24:])
        raise RuntimeError(f"{label} failed (exit {proc.returncode}); log: {log_path}\n{tail}")
    print(f"[{label}] ok; log: {log_path}", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--blender", default="blender", help="Blender executable or full path")
    p.add_argument("--script", type=Path, required=True, help="Scene builder .py accepting --output")
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--name", default="asset", help="File basename: letters/digits/-/_ only")
    p.add_argument("--profile", choices=["game", "render", "print"], default="render")
    p.add_argument("--max-triangles", type=int, default=None)
    p.add_argument("--formats", choices=["glb", "fbx"], nargs="+", default=["glb"])
    p.add_argument("--resolution", type=int, default=720)
    p.add_argument("--samples", type=int, default=32, help="CPU Cycles samples per preview")
    p.add_argument("--allow-qa-errors", action="store_true", help="DRAFT ONLY: bypass critical QA gate")
    p.add_argument("--overwrite", action="store_true", help="Explicitly replace existing delivery files")
    args = p.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.name):
        p.error("--name must contain only letters, digits, '-' or '_'")
    if args.max_triangles is not None and args.max_triangles < 1:
        p.error("--max-triangles must be positive")
    if not 128 <= args.resolution <= 2048:
        p.error("--resolution must be in 128..2048")
    if not 1 <= args.samples <= 256:
        p.error("--samples must be in 1..256")
    scene_script = args.script.expanduser().resolve()
    if not scene_script.is_file() or scene_script.suffix.lower() != ".py":
        p.error("--script must point to a local .py file")
    blender = shutil.which(args.blender)
    if blender is None:
        p.error("Blender executable not found. Install Blender or pass --blender /full/path/to/blender")
    outdir = args.outdir.expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    blend_path = outdir / (args.name + ".blend")
    qa_path = outdir / "qa.json"
    expected = [blend_path, qa_path, outdir / "pipeline_summary.json",
                *(outdir / ("preview_" + v + ".png") for v in ("hero", "front", "side")),
                *(outdir / (args.name + "." + f) for f in set(args.formats))]
    collisions = [str(p) for p in expected if p.exists()]
    if collisions and not args.overwrite:
        p.error("Output files already exist; choose an unused --outdir/--name or explicitly pass "
                "--overwrite: " + ", ".join(collisions))

    # With an explicitly authorized overwrite, remove only known outputs first.
    # Otherwise an earlier successful output could masquerade as a newly produced file.
    if args.overwrite:
        for output in expected:
            if output.is_file() or output.is_symlink():
                output.unlink()

    try:
        run_step(blender, "build", ["--factory-startup", "--python", str(scene_script),
                                    "--", "--output", str(blend_path)], outdir)
        validate_file(blend_path, "blend")
        qa_args = ["--", "--report", str(qa_path), "--profile", args.profile]
        if args.max_triangles is not None:
            qa_args.extend(["--max-triangles", str(args.max_triangles)])
        run_step(blender, "qa", [str(blend_path), "--python", str(HERE / "qa_blender.py"),
                                 *qa_args], outdir)
        if not qa_path.is_file() or qa_path.stat().st_size == 0:
            raise RuntimeError("QA script produced no JSON report")
        qa = json.loads(qa_path.read_text(encoding="utf-8"))
        errors = qa.get("errors")
        warnings = qa.get("warnings")
        if (qa.get("profile") != args.profile or not isinstance(errors, list) or
                not all(isinstance(x, str) for x in errors) or
                not isinstance(warnings, list) or not all(isinstance(x, str) for x in warnings) or
                type(qa.get("total_triangles")) is not int or qa["total_triangles"] < 0):
            raise RuntimeError("QA report has invalid or mismatched schema")
        print(f"[qa] {qa.get('total_triangles', '?')} evaluated triangles, "
              f"{len(errors)} errors, {len(warnings)} warnings", flush=True)
        if errors and not args.allow_qa_errors:
            raise RuntimeError("Critical QA errors prevent export. Check qa.json. "
                               "Repair geometry or use --allow-qa-errors for an explicitly marked draft.")
        run_step(blender, "preview", [str(blend_path), "--python", str(HERE / "render_preview.py"),
                                      "--", "--outdir", str(outdir), "--resolution", str(args.resolution),
                                      "--samples", str(args.samples)], outdir)
        for view in ("hero", "front", "side"):
            preview = outdir / ("preview_" + view + ".png")
            validate_file(preview, "png", args.resolution)
        for format_name in sorted(set(args.formats)):
            export_path = outdir / (args.name + "." + format_name)
            run_step(blender, "export_" + format_name,
                     [str(blend_path), "--python", str(HERE / "export_asset.py"),
                      "--", "--format", format_name, "--output", str(export_path)], outdir)
            validate_file(export_path, format_name)
        summary = {"source": str(blend_path), "exports": args.formats,
                   "qa_errors": errors, "qa_warnings": warnings,
                   "quality_status": "DRAFT_HAS_QA_ERRORS" if errors else "AUTOMATED_QA_PASSED",
                   "generated_previews": ["preview_hero.png", "preview_front.png", "preview_side.png"],
                   "note": "Visual review and target-app validation are still required."}
        (outdir / "pipeline_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print("[done] " + str(outdir), flush=True)
        return 0
    except (RuntimeError, OSError, ValueError, InvalidOutput) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
