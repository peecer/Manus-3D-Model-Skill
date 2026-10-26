"""Parametric, editable example of a modern upholstered wood lounge chair.

Usage:
  blender --background --factory-startup --python modern_chair.py -- --output chair.blend

Not a generalized text-to-3D model. Agents write a NEW builder for each user brief.
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# Primary dimensions (meters); edit these to customize proportions.
WIDTH = 1.04
DEPTH = 0.87
SEAT_Z = 0.56
BASE_WOOD = (0.19, 0.084, 0.038, 1)
FABRIC = (0.025, 0.25, 0.26, 1)
FABRIC_EDGE = (0.014, 0.14, 0.15, 1)
BRASS = (0.65, 0.41, 0.13, 1)


def material(name, color, roughness, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = color
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = color
    p.inputs["Roughness"].default_value = roughness
    p.inputs["Metallic"].default_value = metallic
    return m


def cube(name, center, dimensions, mat, radius=0.012, rotation=(0, 0, 0), segments=3):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center, rotation=rotation)
    o = bpy.context.object
    o.name = name
    o.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    if radius > 0:
        bevel = o.modifiers.new("Soft manufactured edges", "BEVEL")
        bevel.width = min(radius, min(dimensions) * 0.35)
        bevel.segments = segments
        if hasattr(bevel, "affect"):
            bevel.affect = "EDGES"  # Older Blender versions; absent in newer versions
        normal = o.modifiers.new("Corner normals", "WEIGHTED_NORMAL")
        normal.keep_sharp = True
    return o


def cylinder(name, start, end, radius, mat, vertices=24):
    direction = Vector(end) - Vector(start)
    middle = (Vector(start) + Vector(end)) * 0.5
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=direction.length,
                                        location=middle)
    o = bpy.context.object
    o.name = name
    o.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    o.data.materials.append(mat)
    bevel = o.modifiers.new("Edge softening", "BEVEL")
    bevel.width = min(radius * 0.17, 0.008)
    bevel.segments = 2
    for poly in o.data.polygons:
        poly.use_smooth = True
    return o


def build(output_path):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "CYCLES"

    wood = material("01 | walnut satin", BASE_WOOD, 0.37)
    cloth = material("02 | petrol woven upholstery", FABRIC, 0.87)
    piping = material("03 | upholstery piping", FABRIC_EDGE, 0.94)
    metal = material("04 | brushed champagne fasteners", BRASS, 0.33, 0.8)
    charcoal = material("05 | dark rubber glides", (0.018, 0.02, 0.022, 1), 0.82)

    # Four grounded wooden legs, with underseat brace. +Y is back.
    for xsign in (-1, 1):
        for ysign in (-1, 1):
            x = xsign * (WIDTH * 0.40)
            y = ysign * (DEPTH * 0.39)
            cube("Frame | tapered-leg-%+d-%+d" % (xsign, ysign),
                 (x, y, 0.285), (0.077, 0.078, 0.57), wood, radius=0.012)
            cube("Foot | rubber-%+d-%+d" % (xsign, ysign),
                 (x, y, 0.015), (0.081, 0.081, 0.03), charcoal, radius=0.006)

    cube("Frame | front stretcher", (0, -DEPTH * 0.39, 0.42),
         (WIDTH * 0.77, 0.045, 0.065), wood)
    cube("Frame | back stretcher", (0, DEPTH * 0.39, 0.42),
         (WIDTH * 0.77, 0.045, 0.065), wood)
    for xsign in (-1, 1):
        cube("Frame | side stretcher %d" % xsign,
             (xsign * WIDTH * 0.40, 0, 0.43), (0.048, DEPTH * 0.78, 0.066), wood)

    # Seat is a rigid, supported plate plus a cushioned pad with trim.
    cube("Seat | frame", (0, 0, SEAT_Z), (WIDTH, DEPTH, 0.11), wood, radius=0.028)
    cube("Seat | upholstery cushion", (0, -0.015, SEAT_Z + 0.087),
         (WIDTH * 0.91, DEPTH * 0.92, 0.135), cloth, radius=0.061, segments=5)
    cube("Seat | piping seam", (0, -0.015, SEAT_Z + 0.032),
         (WIDTH * 0.923, DEPTH * 0.933, 0.014), piping, radius=0.007)

    # Angled back. Offset rearward as it rises; avoid a thin unsupported plane.
    lean = math.radians(-11)
    for xsign in (-1, 1):
        cube("Back | wooden post %d" % xsign,
             (xsign * WIDTH * 0.41, DEPTH * 0.46, 0.96),
             (0.085, 0.097, 0.80), wood, radius=0.014, rotation=(lean, 0, 0))
    cube("Back | timber crossbar", (0, DEPTH * 0.54, 1.24),
         (WIDTH * 0.78, 0.075, 0.092), wood, radius=0.017)
    cube("Back | inset upholstered panel", (0, DEPTH * 0.475, 1.035),
         (WIDTH * 0.78, 0.16, 0.66), cloth,
         radius=0.065, rotation=(lean, 0, 0), segments=5)
    cube("Back | rear piping trim", (0, DEPTH * 0.535, 1.036),
         (WIDTH * 0.805, 0.021, 0.67), piping,
         radius=0.009, rotation=(lean, 0, 0))

    # Integrated wooden arms, two supports per side and a comfort pad.
    for xsign in (-1, 1):
        x = xsign * (WIDTH * 0.49)
        cube("Arm | forward support %d" % xsign, (x, -0.23, 0.78),
             (0.06, 0.067, 0.36), wood)
        cube("Arm | rear support %d" % xsign, (x, 0.28, 0.78),
             (0.06, 0.067, 0.36), wood)
        cube("Arm | upper rail %d" % xsign, (x, 0.02, 0.982),
             (0.107, 0.72, 0.086), wood, radius=0.026)
        cube("Arm | upholstered comfort pad %d" % xsign, (x, 0.00, 1.037),
             (0.087, 0.62, 0.032), cloth, radius=0.013)
        for y in (-0.23, 0.28):
            cylinder("Detail | brass cap %d %+.2f" % (xsign, y),
                     (xsign * 0.548, y, 0.81), (xsign * 0.555, y, 0.81),
                     0.012, metal, vertices=20)

    # Convenient viewport defaults and professional hierarchy via parent collection.
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.color = o.active_material.diffuse_color if o.active_material else (0.8, 0.8, 0.8, 1)
    bpy.ops.object.select_all(action="DESELECT")
    scene.cursor.location = (0, 0, 0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    print("Saved editable model:", output_path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = p.parse_args(argv)
    build(args.output.resolve())
