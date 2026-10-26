# Blender modeling patterns for the Manus agent

## Reproducibility

- Build in `bpy` using named collections and modular functions (`add_panel`, `add_support`, `add_tube`, `assign_pbr`); expose subject-specific dimensions at top of the script.
- Clear the default scene only in a new dedicated construction file. Don't destroy a user-provided Blender project.
- Set `scene.unit_settings.system = 'METRIC'` and `scale_length = 1.0` unless otherwise required. State the axis convention: Blender +Z up, -Y usually front in previews.
- Add bevel width in real units, prefer a low segment count for realtime, and avoid bevel widths larger than half the narrowest local dimension.
- Mesh primitives can be positioned and transformed by matrix or by object transforms. Apply scale before bevel; maintain meaningful origins. Don't apply armature transforms unintentionally.
- Model built for `.glb` should use the Principled BSDF with consistent Base Color, Roughness and Metallic. Keep shader graphs GLB-compatible when you need to preserve material appearance.

## Dimensioned blockout

1. Establish ground plane Z=0 and a nominal object bounding box (meters).
2. Build largest masses first and render front/side/3/4 previews.
3. Adjust bounding box and primary shapes; only then add bevels and details.
4. For reference photos, identify camera perspective; avoid matching foreshortened screen distances literally to 3D proportions.
5. Distinguish intentional multi-mesh assemblies from accidental intersections or z-fighting.

## Shading

- For bevelled cubes use `BevelModifier` with `segments = 2..4`, limited width, and optionally a `WeightedNormalModifier` if supported.
- Smooth polygons only where appropriate. Weighted normals fix many hard-surface artifacts but cannot fix incorrect geometry.
- Use actual materials instead of viewport-only colors. A single untextured node color is not an equivalent to a full PBR texture set.

## Visual QA

Inspect at least:

- Three-quarter view: overall readability and assembly.
- Front view: widths, symmetry, spacing.
- Side view: depth, tilt, thickness.
- Optional top/back and wireframe screenshots for complex objects.
- Compare with the source image or brief at similar angles. Adjust proportions before increasing detail.

## Organic models

Procedural primitives alone rarely give convincing humans, animals, foliage, or irregular natural surfaces. Use genuinely suitable sculpting, curves, retopology, geometry nodes, or compatible generation tools when available. For deformation/animation, inspect topology around joints under test poses. If the execution environment only supports headless scripting, disclose the reduced confidence in likeness and animation-ready topology.

## Scene script contract

Implement a command-line `--output <absolute-path>` argument after Blender's `--`. Save to that exact path via `bpy.ops.wm.save_as_mainfile(filepath=...)`. Do not add presentation-only floors or backgrounds to the export scene; the preview script will produce lights/cameras non-destructively. The model remains editable.
