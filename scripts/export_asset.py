"""Non-destructive asset exports run from a loaded .blend project."""
import argparse
import sys
from pathlib import Path

import bpy


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--format", choices=["glb", "fbx"], required=True)
    p.add_argument("--output", type=Path, required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = p.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    assets = [o for o in bpy.context.scene.objects
              if o.type in {"MESH", "CURVE", "FONT", "EMPTY", "ARMATURE"}
              and not o.name.startswith(("COL_", "_HELPER_"))
              and not o.hide_render]
    if not assets:
        raise RuntimeError("No asset objects available for export")
    for obj in assets:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = next((o for o in assets if o.type == "MESH"), assets[0])
    if args.format == "glb":
        if not hasattr(bpy.ops.export_scene, "gltf"):
            raise RuntimeError("glTF exporter not available in this Blender installation")
        bpy.ops.export_scene.gltf(filepath=str(args.output), export_format="GLB",
                                  use_selection=True, export_cameras=False, export_lights=False)
    else:
        bpy.ops.export_scene.fbx(filepath=str(args.output), use_selection=True,
                                 bake_anim=False, use_mesh_modifiers=True,
                                 add_leaf_bones=False, path_mode="AUTO")
    print("Exported", args.output)


if __name__ == "__main__":
    main()
