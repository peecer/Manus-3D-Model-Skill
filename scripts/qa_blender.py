"""Run inside Blender via: blender --background model.blend --python qa_blender.py -- --report qa.json"""
import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector


def after_dash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def fvec(vector):
    return [round(float(x), 6) for x in vector]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--profile", choices=["game", "render", "print"], default="render")
    parser.add_argument("--max-triangles", type=int)
    args = parser.parse_args(after_dash())

    report = {"profile": args.profile, "blender_version": bpy.app.version_string,
              "errors": [], "warnings": [], "objects": [], "total_triangles": 0,
              "total_vertices": 0, "material_count": 0, "bounds_m": None,
              "limitations": ["Does not detect UV overlap/distortion, self-intersections, "
                              "minimum wall thickness, functional tolerances, or visual likeness."]}
    mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render
                 and not o.name.startswith(("COL_", "_HELPER_"))]
    if not mesh_objs:
        report["errors"].append("Scene contains no renderable asset meshes.")
    scene = bpy.context.scene
    if scene.unit_settings.system != "METRIC" or abs(scene.unit_settings.scale_length - 1.0) > 1e-7:
        report["warnings"].append("Scene does not use the default 1-unit-per-meter metric convention; verify scale.")

    all_mat = set()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    min_xyz = Vector((math.inf,) * 3)
    max_xyz = Vector((-math.inf,) * 3)
    for obj in mesh_objs:
        obj_eval = obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()
        if mesh is None:
            report["errors"].append(f"{obj.name}: evaluated mesh is unavailable")
            continue
        try:
            # Blender 4.1+ removed calc_loop_triangles(); every n-gon triangulates to n-2 faces.
            verts = len(mesh.vertices)
            tris = sum(max(0, len(poly.vertices) - 2) for poly in mesh.polygons)
            polys = len(mesh.polygons)
            report["total_vertices"] += verts
            report["total_triangles"] += tris
            if not verts or not polys:
                report["errors"].append(f"{obj.name}: empty mesh or no faces")
            bad_coords = sum(1 for v in mesh.vertices if not all(math.isfinite(c) for c in v.co))
            if bad_coords:
                report["errors"].append(f"{obj.name}: {bad_coords} vertices contain NaN/Inf")
            bm = bmesh.new()
            try:
                bm.from_mesh(mesh)
                boundary = sum(1 for e in bm.edges if e.is_boundary)
                nonmanifold = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
                loose = sum(1 for v in bm.verts if not v.link_faces)
                degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
            finally:
                bm.free()
            if degenerate:
                report["errors"].append(f"{obj.name}: {degenerate} near-zero-area faces")
            if loose:
                report["warnings"].append(f"{obj.name}: {loose} vertices without faces")
            if boundary or nonmanifold:
                issue = f"{obj.name}: {boundary} boundary edges, {nonmanifold} non-manifold/wire edges"
                if args.profile == "print":
                    report["errors"].append(issue)
                else:
                    report["warnings"].append(issue)
            if any(abs(float(s) - 1.0) > 1e-5 for s in obj.scale):
                report["warnings"].append(f"{obj.name}: unapplied scale {fvec(obj.scale)}")
            if obj.matrix_world.determinant() < 0:
                report["warnings"].append(f"{obj.name}: mirrored negative-determinant world transform")
            if not obj.data.materials:
                report["warnings"].append(f"{obj.name}: no assigned surface material")
            if args.profile == "game" and not obj.data.uv_layers:
                report["warnings"].append(f"{obj.name}: no UV map (okay for solid-color GLB materials)")
            for mat in obj.data.materials:
                if mat:
                    all_mat.add(mat.name)
            # Use evaluated vertex locations to include modifier-driven geometry in dimensions.
            for vert in mesh.vertices:
                world = obj_eval.matrix_world @ vert.co
                for axis in range(3):
                    min_xyz[axis] = min(min_xyz[axis], world[axis])
                    max_xyz[axis] = max(max_xyz[axis], world[axis])
            report["objects"].append({"name": obj.name, "triangles": tris, "vertices": verts,
                                      "faces": polys, "boundary_edges": boundary,
                                      "non_manifold_edges": nonmanifold, "degenerate_faces": degenerate})
        finally:
            obj_eval.to_mesh_clear()

    report["material_count"] = len(all_mat)
    if mesh_objs and all(math.isfinite(x) for x in min_xyz) and all(math.isfinite(x) for x in max_xyz):
        report["bounds_m"] = {"min": fvec(min_xyz), "max": fvec(max_xyz),
                              "dimensions": fvec(max_xyz - min_xyz)}
    if args.max_triangles is not None and report["total_triangles"] > args.max_triangles:
        report["errors"].append(f"Triangle budget exceeded: {report['total_triangles']} > {args.max_triangles}")
    for img in bpy.data.images:
        if img.source == "FILE" and not img.packed_file:
            if img.filepath and not os.path.isfile(bpy.path.abspath(img.filepath)):
                report["errors"].append(f"Missing external texture: {img.name} ({img.filepath})")

    report["automated_check"] = "FAIL" if report["errors"] else "PASS_WITH_WARNINGS" if report["warnings"] else "PASS"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"result": report["automated_check"], "triangles": report["total_triangles"],
                      "errors": len(report["errors"]), "warnings": len(report["warnings"])}, indent=2))


if __name__ == "__main__":
    main()
