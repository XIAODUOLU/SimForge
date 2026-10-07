# Compatibility strategy and validation scope

For installation, see the [README](../README.md#installation). For build commands and adapter examples, see the [development guide](development.md). Processing requirements are defined in the [architecture](architecture.md).

## Versions and installation

| Range | Package | Validation status |
| --- | --- | --- |
| Blender 4.0–4.1 | Legacy ZIP, `bl_info` minimum 4.0 | Pending tests in actual versions |
| Blender 4.x | Extension ZIP where supported; legacy ZIP for 4.0–4.1 | Registration/interface smoke tests and Extension manifest validation pass in the available local runtime; other releases remain unverified |
| Blender 5.x | Extension ZIP | Known USD argument changes adapted; runtime tests pending |

The Extension manifest requires 4.2 because that installation format starts with 4.2; the business code targets 4.0 and later. Both the manifest and runtime check exclude 6.0. Passing tests in one version does not establish coverage of every 4.x/5.x release.

Validation uses the locally available Blender 4.x executable. The smoke test covers registration, unregistration, re-registration, placeholder cancellation, input/path checks, parameter forwarding, result contracts and USD exporter argument adaptation. Extension validation checks the source manifest. Processing services remain placeholders: real retopology, UV generation, texture baking, USD physics authoring and Isaac Sim behavior have not been validated. The simulated Blender 5.x RNA branch is a unit-level compatibility check, not a Blender 5.x runtime test. Manual installation and UI checks remain pending.

## Adapter boundaries

1. Use `get_rna_type().properties` to inspect actual Operator capabilities; `hasattr(bpy.ops...)` does not reliably prove an Operator exists.
2. Report missing required arguments or unsupported enum values immediately instead of silently omitting them and changing results.
3. Prefer `export_textures_mode='NEW'` when available; older versions use `export_textures=True`. The helper supplies common arguments only. Selection isolation, units, resource paths and physics remain the export implementation's responsibility.
4. Access Principled inputs by name to avoid socket index changes between versions.
5. Do not load pxr, PhysxSchema or 3D Print Toolbox during registration. Blender's USD exporter and importable USD Python bindings are separate capabilities.
6. Use syntax supported by the Python bundled with the minimum supported Blender 4.x release. Modules declaring RNA properties must not use postponed annotations.
7. UV/QuadriFlow, transparent material settings, Cycles and full USD export arguments still need adaptation during algorithm implementation. The scaffold does not guarantee compatibility of arbitrary future implementations.

## Validation procedure

Run each target Blender executable:

```bash
/path/to/blender -b --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
/path/to/blender -b --factory-startup --command extension validate simforge
```

Suggested coverage includes Blender 4.x and 5.x releases used for delivery, with separate legacy-package checks for 4.0–4.1. The Extension validation command applies only to releases supporting Extensions. Manually check installation → enable → sidebar → save/reopen → disable → re-enable. Once algorithms are implemented, add small real assets covering non-manifold inputs, multiple material slots, transparency, constant metallic values, negative scales, different units and paths containing spaces or Chinese characters.

## Official references

- [Blender 5.x USD API migration](https://developer.blender.org/docs/release_notes/5.0/python_api/): replacement of USD `export_textures` with `export_textures_mode`.
- [Extension manifest schema](https://developer.blender.org/docs/features/extensions/schema/1.0.0/): version and file permission declarations.
- [Blender USD Operators](https://docs.blender.org/api/current/bpy.ops.wm.html#bpy.ops.wm.usd_export): use runtime RNA as the authority for available arguments.
- [Isaac Sim Physics Fundamentals](https://docs.isaacsim.omniverse.nvidia.com/latest/physics/simulation_fundamentals.html): USD Physics, collision and rigid-body semantics.
- [Omni Physics Colliders](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/rigid_bodies_articulations/collision.html): collision approximations and dynamic mesh limitations.
