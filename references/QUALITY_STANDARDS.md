# Quality standards — reference-driven 3D creation

## Required proof, not slogans

Each task produces a spec, a `.blend` project, QA JSON, and renders from 3/4, front, and side (unless user asks for different views). Compare **actual renders** to references; a render command finishing successfully does not mean the model is correct. Record the remaining uncertainty explicitly.

## Modeling review rubric (0–5 each, qualitative)

1. **Recognizability:** subject and distinctive features read instantly.
2. **Proportions:** silhouette, scale, offsets and negative space follow requirements.
3. **Construction:** intersections, functional seams, supports and meaningful thickness make sense.
4. **Geometry/shading:** no apparent pinching, extreme faceting, accidental holes, z-fighting, or wavy shading.
5. **Materials/lighting:** surfaces communicate their material, with clear roughness/metal behavior and legible lighting.
6. **Handoff:** named objects/collections, editable source, consistent scale/orientation, requested format and textures.

If any dimension scores below 4/5, improve it or disclose why it cannot be improved with the available tools. Do not present subjective rubric scores as objectively validated facts.

## Game / real-time assets

- Set a triangle budget and measure evaluated mesh triangle counts.
- Maintain silhouette where prominent; reduce unnecessary hidden geometry.
- UV unwrap texture-mapped geometry, avoid unintended UV overlap when baking, use bake cage and normal-map convention appropriate to the target renderer.
- Ensure PBR texture paths exist and exports carry or correctly reference them. Test actual import into the target engine when it is available.
- Use meaningful asset origins and object naming; ensure consistent orientation and scale. Collision proxies, LODs, skinning and animations are task-specific—not inferred as completed.
- Non-manifold individual meshes can be valid for intentionally open single-sided props, but report them.

## Product and visualization assets

- Use precise dimensions where known; bevel radii, wall thickness, edge flow, and highlights should be intentional.
- Separate materials by physical component, not arbitrary shader splashes.
- Use realistic roughness ranges and broad lights to reveal defects; inspect dark and shiny areas for shading artifacts.
- Check front/side/three-quarter silhouette and at least one closer detail image for intricate subjects.

## 3D-print assets

- Every independently printable closed shell needs manifold topology (no boundary or >2-face edges), consistent normals, minimum practical wall thickness, no coincident/self-intersecting surfaces, and tolerances for mating parts.
- The included `qa_blender.py` checks basic topology but **does not** reliably detect self-intersections, wall thickness, trapped volumes, or printer-specific constraints. Those require additional tools and inspection.
- Avoid assuming visual overlap makes a watertight union; use boolean unions or deliberate print assembly, then recheck.

## Known limits of automated QA

Automatic checks can count triangles, find some topology issues, and detect missing external image files. They cannot reliably judge artistic quality, accuracy to an ambiguous picture, UV overlap/distortion, mesh self-intersections, functional tolerances, rig quality, animation deformation, or manufacturing certification. Do not represent a passing JSON report as a guarantee of those properties.
