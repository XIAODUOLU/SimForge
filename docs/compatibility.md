# Compatibility strategy and validation scope

For installation, see the [README](../README.md#installation). For build commands and adapter examples, see the [development guide](development.md). Processing requirements are defined in the [architecture](architecture.md).

## Versions and installation

| Range | Package | Validation status |
| --- | --- | --- |
| Blender 4.0–4.1 | Legacy ZIP, `bl_info` minimum 4.0 | Installation, enable/reopen/re-enable, Retopo, GPU Bake and USD Export validated in Blender 4.x |
| Blender 4.2–4.x | Extension ZIP | Extension compatibility checked in Blender 4.x |
| Blender 5.x | Extension ZIP | Manifest/package validation, installation, enable/reopen/re-enable, Retopo, GPU Bake and USD Export validated in Blender 5.x |

The Extension manifest requires 4.2 because that installation format starts with 4.2; the business code targets 4.0 and later. Both the manifest and runtime check exclude 6.0. Passing tests in one version does not establish coverage of every 4.x/5.x release.

Existing validation covers registration, input/path checks, parameter forwarding, result contracts and USD exporter argument adaptation. Real USD tests cover dynamic/static bodies, both collision approximations, physics materials, modifier evaluation, negative/nonuniform scale, parent transforms, units, texture relocation and failure cleanup. Pip installation and cached dependency reuse are tested with Blender's Python in temporary user data. The real pipeline runs in Blender 4.x and 5.x, including GPU baking of all five channels. Small constant-material fixtures produced matching channel values in both version families. This does not establish image quality for arbitrary input meshes or material graphs.

Physics properties and simulation behavior of assets exported from Blender 4.x and 5.x were tested in Isaac Sim 6.x. The reusable asset intentionally has no global physics scene; the validation scene adds one.

## Adapter boundaries

1. Use `get_rna_type().properties` to inspect actual Operator capabilities; `hasattr(bpy.ops...)` does not reliably prove an Operator exists.
2. Report missing required arguments or unsupported enum values immediately instead of silently omitting them and changing results.
3. Prefer `export_textures_mode='NEW'` when available; older versions use `export_textures=True`. The helper supplies common arguments only. Selection isolation, units, resource paths and physics remain the export implementation's responsibility.
4. Access Principled inputs by name to avoid socket index changes between versions.
5. Registration checks USD bindings and installs missing `usd-core` with Blender's own Python pip into plugin user data. Working native bindings take priority. This requires network access only on the first missing-dependency installation. `PhysxSchema` is not needed for the implemented export and is not supplied by `usd-core`.
6. Use syntax supported by the Python bundled with the minimum supported Blender 4.x release. Modules declaring RNA properties must not use postponed annotations.
7. Alpha baking connects a Non-Color grayscale texture to the target Alpha input. The adapter uses `surface_render_method` when available, otherwise `blend_method`. Cycles GPU baking requires a configured device in Blender preferences.

## Validation procedure

Run each target Blender executable:

```bash
/path/to/blender -b --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
/path/to/blender -b --factory-startup --python-exit-code 1 --python tests/blender_export.py
/path/to/blender -b --factory-startup --python-exit-code 1 --python tests/blender_dependencies.py
/path/to/blender -b --factory-startup --python-exit-code 1 --python tests/blender_pipeline.py
/path/to/blender -b --factory-startup --command extension validate simforge
```

To reproduce Isaac Sim checks, generate four fixtures with each Blender version, then run the headless validation script from Isaac Sim's Python environment:

```bash
/path/to/blender -b --factory-startup --python-exit-code 1 --python tests/blender_isaac_fixtures.py -- /tmp/simforge-assets
/path/to/isaacsim/python.sh tests/isaac_assets.py /tmp/simforge-assets --/renderer/enabled=false --/app/window/enabled=false --/app/livestream/enabled=false
```

Suggested coverage includes Blender 4.x and 5.x releases used for delivery, with separate legacy-package checks for 4.0–4.1. The Extension validation command applies only to releases supporting Extensions. Package installation → enable → save/reopen → disable → re-enable was checked headlessly in Blender 4.x and 5.x; visual sidebar inspection remains a manual UI check. Add real assets covering non-manifold inputs, complex material graphs, negative scales, different units and paths containing spaces or Chinese characters when validating new releases.

## Official references

- [Blender 5.x USD API migration](https://developer.blender.org/docs/release_notes/5.0/python_api/): replacement of USD `export_textures` with `export_textures_mode`.
- [Extension manifest schema](https://developer.blender.org/docs/features/extensions/schema/1.0.0/): version and file permission declarations.
- [Blender USD Operators](https://docs.blender.org/api/current/bpy.ops.wm.html#bpy.ops.wm.usd_export): use runtime RNA as the authority for available arguments.
- [Isaac Sim Physics Fundamentals](https://docs.isaacsim.omniverse.nvidia.com/latest/physics/simulation_fundamentals.html): USD Physics, collision and rigid-body semantics.
- [Omni Physics Colliders](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/rigid_bodies_articulations/collision.html): collision approximations and dynamic mesh limitations.
- [usd-core on PyPI](https://pypi.org/project/usd-core/): core USD Python bindings, including standard USD Physics.
