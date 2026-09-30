# Compatibility strategy and validation scope

For installation, see the [README](../README.md#installation). For build commands and adapter examples, see the [development guide](development.md). Processing requirements are defined in the [architecture](architecture.md).

## Versions and installation

| Range | Package | Validation status |
| --- | --- | --- |
| Blender 4.0–4.1 | Legacy ZIP, `bl_info` minimum 4.0 | Pending tests in actual versions |
| Blender 4.2.3 LTS | Extension or legacy ZIP | Registration and interfaces tested in process |
| Other Blender 4.x | Extension ZIP | Pending tests in actual versions |
| Blender 5.x | Extension ZIP | Known USD argument changes adapted; runtime tests pending |

The Extension manifest requires 4.2 because that installation format starts with 4.2; the business code targets 4.0 and later. Both the manifest and runtime check exclude 6.0. Passing tests in one version does not establish coverage of every 4.x/5.x release.

## Adapter boundaries

1. Use `get_rna_type().properties` to inspect actual Operator capabilities; `hasattr(bpy.ops...)` does not reliably prove an Operator exists.
2. Report missing required arguments or unsupported enum values immediately instead of silently omitting them and changing results.
3. Prefer `export_textures_mode='NEW'` when available; older versions use `export_textures=True`. The helper supplies common arguments only. Selection isolation, units, resource paths and physics remain the export implementation's responsibility.
4. Access Principled inputs by name to avoid socket index changes between versions.
5. Do not load pxr, PhysxSchema or 3D Print Toolbox during registration. Blender's USD exporter and importable USD Python bindings are separate capabilities.
6. Use syntax supported by the Python bundled with Blender 4.0. Modules declaring RNA properties must not use postponed annotations.
7. UV/QuadriFlow, transparent material settings, Cycles and full USD export arguments still need adaptation during algorithm implementation. The scaffold does not guarantee compatibility of arbitrary future implementations.

## Validation procedure

Run each target Blender executable:

```bash
/path/to/blender -b --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
```

Suggested coverage includes 4.0, 4.1, 4.2 LTS, 4.5 LTS, 5.0 and any other release used for delivery. Manually check installation → enable → sidebar → save/reopen → disable → re-enable. Once algorithms are implemented, add small real assets covering non-manifold inputs, multiple material slots, transparency, constant metallic values, negative scales, different units and paths containing spaces or Chinese characters.

## Official references

- [Blender 5.0 Python API changes](https://developer.blender.org/docs/release_notes/5.0/python_api/): removal of USD `export_textures`.
- [Extension manifest schema](https://developer.blender.org/docs/features/extensions/schema/1.0.0/): version and file permission declarations.
- [Blender USD Operators](https://docs.blender.org/api/current/bpy.ops.wm.html#bpy.ops.wm.usd_export): use runtime RNA as the authority for available arguments.
- [Isaac Sim Physics Fundamentals](https://docs.isaacsim.omniverse.nvidia.com/latest/physics/simulation_fundamentals.html): USD Physics, collision and rigid-body semantics.
- [Omni Physics Colliders](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/rigid_bodies_articulations/collision.html): collision approximations and dynamic mesh limitations.
