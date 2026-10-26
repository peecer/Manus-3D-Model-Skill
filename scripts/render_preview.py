"""Render repeatable studio views without modifying the saved asset file."""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def make_material():
    mat = bpy.data.materials.new("_Preview_Backdrop")
    mat.diffuse_color = (0.26, 0.29, 0.33, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.30, 0.33, 0.37, 1)
        bsdf.inputs["Roughness"].default_value = 0.82
    return mat


def light(name, location, power, area_size, center):
    datablock = bpy.data.lights.new(name=name, type="AREA")
    datablock.energy = power
    datablock.shape = "DISK"
    datablock.size = area_size
    obj = bpy.data.objects.new(name, datablock)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, center)
    return obj


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--resolution", type=int, default=720)
    p.add_argument("--samples", type=int, default=32)
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    args.outdir.mkdir(parents=True, exist_ok=True)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render
              and not o.name.startswith(("COL_", "_HELPER_"))]
    if not meshes:
        raise RuntimeError("No visible asset meshes to render")
    min_v = Vector((math.inf, math.inf, math.inf))
    max_v = Vector((-math.inf, -math.inf, -math.inf))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        for corner in evaluated.bound_box:
            point = evaluated.matrix_world @ Vector(corner)
            for i in range(3):
                min_v[i] = min(min_v[i], point[i])
                max_v[i] = max(max_v[i], point[i])
    center = (min_v + max_v) * 0.5
    ext = max_v - min_v
    span = max(float(max(ext)), 0.5)
    bottom = float(min_v.z)

    world = bpy.context.scene.world or bpy.data.worlds.new("Preview World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.40, 0.45, 0.53, 1.0)
        bg.inputs["Strength"].default_value = 0.55

    # Presentation-only stage: this script never saves the .blend project.
    bpy.ops.mesh.primitive_plane_add(size=1, location=(center.x, center.y, bottom - 0.012 * span))
    stage = bpy.context.object
    stage.name = "_Preview_Floor"
    stage.scale = (span * 5.0, span * 5.0, 1)
    stage.data.materials.append(make_material())

    light("_Preview_Key", center + Vector((-2.0, -3.1, 4.5)) * span,
          650 * span * span, 3.0 * span, center)
    light("_Preview_Fill", center + Vector((3.1, -0.5, 2.8)) * span,
          400 * span * span, 2.5 * span, center)
    light("_Preview_Rim", center + Vector((1.1, 3.5, 3.6)) * span,
          850 * span * span, 2.1 * span, center)

    camera_data = bpy.data.cameras.new("_Preview_Orthographic")
    camera = bpy.data.objects.new("_Preview_Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = span * 1.85
    bpy.context.scene.camera = camera

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2
    try:
        scene.view_settings.view_transform = "AgX"
    except (TypeError, ValueError):
        scene.view_settings.view_transform = "Standard"

    views = {
        "hero": Vector((1.5, -2.5, 1.45)),
        "front": Vector((0, -3.0, 0.42)),
        "side": Vector((3.0, 0, 0.42)),
    }
    for name, direction in views.items():
        camera.location = center + direction.normalized() * max(span * 3.5, 2.0)
        look_at(camera, center)
        scene.render.filepath = str(args.outdir / ("preview_" + name + ".png"))
        bpy.ops.render.render(write_still=True)
        print("Rendered", scene.render.filepath)


if __name__ == "__main__":
    main()
