# Development guide

This guide explains how to implement SimForge services and use their supporting adapters. Read the [architecture and processing contracts](architecture.md) before implementing a stage, and consult the [compatibility guide](compatibility.md) when handling Blender API differences.

## Service entry points

| Module | Function | Required result |
| --- | --- | --- |
| `simforge/services/retopo.py` | `retopo(context, high_poly, options)` | `RetopoResult` with an independent mesh and active, packed UVs |
| `simforge/services/bake.py` | `bake(context, high_poly, low_poly, options, output_directory)` | `BakeResult` with saved textures for every requested channel |
| `simforge/services/export.py` | `export(context, low_poly, options)` | `ExportResult` pointing to the final USD with physics authored |

The service entry points are implemented. External scripts may call them directly, but must satisfy their preconditions. Examples below are fragments intended for service modules; they are not complete algorithms or standalone scripts.

The existing call chain is:

```text
Panel → Operator → Workflow validation → Your service function → Adapters
```

Workflow creates an options snapshot from panel settings. Services should read `options.target_faces`, for example, rather than accessing `context.scene.simforge` directly. Do not import UI or workflow modules into services.

## Preconditions and ownership

| Layer | Existing responsibility | What service implementations still need to do |
| --- | --- | --- |
| Operator | Require Object Mode; display expected errors and log unexpected exceptions | Keep all bpy operations on the main thread and restore temporary state |
| Workflow | Check nonempty Mesh inputs and View Layer membership; require active UVs for Bake/Export; reject shared source/target mesh data for Bake | Check geometry quality, usable UV layout, visibility/selectability, materials, and algorithm-specific requirements |
| Workflow | Resolve output paths; reject existing USD destinations; check returned objects/files | Create directories, validate file contents, handle overwrite races, and clean up failed output |
| Service | Own algorithms and temporary resources | Validate the complete result before returning |

Direct service calls bypass Operator and Workflow checks. Callers must establish valid inputs and context; services should also validate assumptions before making changes. Dataclass annotations do not enforce runtime types or numeric ranges, and direct callers bypass the limits imposed by UI properties.

Workflow checks that a UV layer exists, not that it is properly unwrapped or packed. It checks file existence, not image contents or USD schemas. A successful return must therefore mean the service has already validated its output. If workflow rejects a result after a service returns, it does not automatically remove that service's objects or files.

## Options and units

| Option | Meaning |
| --- | --- |
| `RetopoOptions.target_faces` | Requested face count, not an exact-count guarantee |
| `RetopoOptions.voxel_size` | Size of the voxel; use a consistent coordinate space |
| `RetopoOptions.smart_uv_angle` | Radians |
| `RetopoOptions.uv_margin` | UV-space spacing; explicitly choose and validate Pack Islands margin semantics |
| `BakeOptions.resolution` | Texture dimension in pixels |
| `BakeOptions.cage_extrusion` | Blender scene length units |
| `BakeOptions.channels` | Unique requested `BakeChannel` values; defaults to normal, base color, metallic, roughness and alpha |
| `ExportOptions.meters_per_blender_unit` | Scale used to convert scene coordinates to meters |
| `ExportOptions.physics` | Body type, mass in kilograms, collision approximation, friction, and restitution |

Treat options as immutable. Iterate over `options.channels` rather than assuming a hardcoded list. Return absolute `Path` values for saved textures so results do not depend on the process working directory.

Metallic, roughness and alpha use emission baking in temporary copies of each source material. The service routes the corresponding Principled input through an Emission node, handling constants and linked scalar inputs. Input graphs may contain textures, procedural nodes and node groups; the surface shader itself must be one directly connected Principled BSDF, optionally through reroutes. Data maps, including normal and alpha, use Non-Color; base color uses sRGB.

The sidebar requests all five channels. A direct caller can select a subset with `BakeOptions(channels=(BakeChannel.METALLIC, BakeChannel.ROUGHNESS, BakeChannel.ALPHA))`. Successful results contain absolute PNG paths for every requested channel and a connected target material. Alpha is stored as grayscale RGB and connects through the Image Texture Color output. Output files are not overwritten.

## Adapter reference

| Helper | Recommended use | What it does |
|---|---|---|
| `preserve_selection(context)` | All three services | Restores selected objects and the active object |
| `checked_kwargs(...)` | Retopo, UV operations, baking | Checks operator arguments against the current Blender API |
| `principled_input(node, name)` | Bake | Retrieves a Principled BSDF input by name |
| `enable_material_alpha(material)` | Bake | Enables transparent rendering through the available material API |
| `usd_export_kwargs(filepath)` | Export | Builds USD export arguments for the current Blender version |
| `require_usd()` | Export | Loads USD Python modules when needed |
| `ensure_supported_version()` | Already called during registration | Checks the Blender version range |
| `operator_properties(operator)` | Custom compatibility logic | Exposes an operator’s available RNA properties |

These helpers provide specific building blocks. They do not perform complete retopology, baking, or export.

## Preserve selection

Inside any service:

```python
from ..adapters.context import preserve_selection

with preserve_selection(context):
    for obj in tuple(context.selected_objects):
        obj.select_set(False)

    low_poly.select_set(True)
    context.view_layer.objects.active = low_poly

    # Perform operations that require the target to be active.
```

When the block exits, it restores the original selection and active object, including when an exception occurs.

**Important limitations:** enter and exit in Object Mode, and preserve the original input objects. This helper does not restore render settings, materials, visibility, or files. If your code enters Edit Mode, restore Object Mode in your own `finally` block.

## Check operator arguments

For example, inside your Retopo implementation:

```python
import bpy

from ..adapters.blender import checked_kwargs
from ..core.errors import SimForgeError

# The caller must already have established the correct editing context.
arguments = checked_kwargs(
    bpy.ops.uv.smart_project,
    required={
        "angle_limit": options.smart_uv_angle,
    },
)

result = bpy.ops.uv.smart_project(**arguments)

if "FINISHED" not in result:
    raise SimForgeError("Smart UV Project did not complete.")
```

`checked_kwargs()`:

- Raises `CompatibilityError` if a required argument is unavailable.
- Checks ordinary enum values.
- Omits unavailable arguments supplied through `optional`.

Only classify an argument as optional when omitting it cannot compromise the output. UV spacing requirements should not silently disappear.

It **does not** establish the correct mode or selection, validate every numeric range, or execute the operator. Keep `required` and `optional` keys disjoint: the current helper merges optional values after required values, so a duplicate optional key would override a required value.

Smart UV Project is only one step. Your Retopo implementation must also select the intended mesh elements, run Pack Islands with explicit margin semantics, verify the resulting UVs, and return to Object Mode. Use `try/finally` around mode changes so selection restoration can run in the expected context.

## Access material inputs

```python
from ..adapters.blender import principled_input

metallic_socket = principled_input(principled_node, "Metallic")

if metallic_socket.is_linked:
    source_socket = metallic_socket.links[0].from_socket
    # Route the source through your temporary baking material.
else:
    metallic_value = metallic_socket.default_value
    # Bake the constant value through your temporary material.
```

The helper retrieves and validates the socket. It does not evaluate a linked node graph or create temporary materials. Make material copies before changing source shading.

## Use the USD export helpers

Inside `services/export.py`, pass a staging path owned by the current operation. The following fragment assumes `staging_directory` already exists next to the destination and will hold the temporary USD and its resources:

```python
import bpy

from ..adapters.blender import usd_export_kwargs
from ..adapters.context import preserve_selection
from ..core.errors import SimForgeError

staged_usd = staging_directory / options.filepath.name

with preserve_selection(context):
    for obj in tuple(context.selected_objects):
        obj.select_set(False)

    low_poly.select_set(True)
    context.view_layer.objects.active = low_poly

    arguments = usd_export_kwargs(staged_usd)
    result = bpy.ops.wm.usd_export(**arguments)

    if "FINISHED" not in result:
        raise SimForgeError("USD export did not complete.")
```

This illustrates the **geometry/material export step only**. Author physics on the staged USD, then validate units, schemas, materials, and texture paths before committing output. Publish textures and the USD with their relative directory layout preserved; moving only the USD can break resource references. Clean up only files owned by the current operation and return the final destination path after a successful commit.

The implementation must define how to handle an existing texture directory, a destination created after workflow validation, and failures during multi-file publication. Temporary staging alone is not a complete transaction. `usd_export_kwargs()` also does not establish meters, Z-up, `defaultPrim`, or physics schemas.

Load USD bindings when you reach the physics step:

```python
from ..adapters.usd import require_usd

modules = require_usd()
Usd = modules["Usd"]
UsdPhysics = modules["UsdPhysics"]
```

For PhysX-specific features:

```python
modules = require_usd(with_physx=True)
PhysxSchema = modules["PhysxSchema"]
```

The function returns module objects, not an opened stage. Missing core bindings are installed with Blender's Python pip into `simforge_dependencies` in the user scripts directory. Registration performs the same check, so exports normally reuse already loaded bindings. Pip is bootstrapped from Blender's bundled ensurepip if needed. Installation failures report an error and leave no partially installed cache. PhysX-specific bindings require a separate NVIDIA runtime.

## Results and error handling

**Return the defined result types.** Workflow inspects their fields after the service returns. These fragments belong inside their respective functions.

Retopo, after creating and validating an independent mesh with packed UVs:

```python
from ..core.contracts import RetopoResult

return RetopoResult(low_poly=low_poly)
```

Bake, after saving and validating every requested texture:

```python
from ..core.contracts import BakeResult

# Map each requested BakeChannel to the absolute Path of its saved image.
return BakeResult(textures=saved_textures)
```

Build `saved_textures` while iterating over `options.channels`. Keys are `BakeChannel` members such as `BakeChannel.NORMAL`; every requested channel must be present.

Export, after committing and validating the final asset:

```python
from ..core.contracts import ExportResult

return ExportResult(filepath=options.filepath)
```

**Raise `SimForgeError` for expected failures:**

```python
from ..core.errors import SimForgeError

raise SimForgeError("The repaired mesh is still non-manifold.")
```

The existing Operator displays the message and cancels the operation. You do not need to call `self.report()` inside services.

**Use `try/finally` for temporary changes.** For example:

```python
original_engine = context.scene.render.engine

try:
    context.scene.render.engine = "CYCLES"
    # Perform baking.
finally:
    context.scene.render.engine = original_engine
```

Apply the same pattern to other settings you modify. `CANCELLED` does not automatically clean up partial meshes, temporary materials, or written files.

Implement Retopo and its result contract first, then Bake, then Export. Changes to `ui.py`, `operators.py`, and `registration.py` are only needed for new settings or interaction behavior.

## Local development

Use the repository as the source of truth, then rebuild and reinstall the appropriate ZIP when testing the installed add-on. Editing repository files does not update an already installed copy.

Restart Blender after reinstalling changed Python modules. Disabling and re-enabling alone does not guarantee that imported modules are reloaded. Avoid loading legacy and Extension installations of SimForge simultaneously: both register the same operator identifiers and scene property.

The examples use relative imports intended for modules inside `simforge/services/`; pasting them into Blender's Text Editor as standalone scripts will not resolve those imports. The smoke test adds the repository root to `sys.path` and tests source code directly, rather than the installed ZIP.

## Build and validation

Run these commands from the repository root:

```bash
python3 scripts/build.py
blender -b --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
blender -b --factory-startup --python-exit-code 1 --python tests/blender_export.py
blender -b --factory-startup --python-exit-code 1 --python tests/blender_dependencies.py
python3 -m compileall -q simforge scripts tests
blender -b --factory-startup --command extension validate simforge
```

The Extension validation command requires Blender 4.2 or later. The build script produces legacy and Extension ZIP packages in `dist/` and includes the root MIT license in both.

Smoke tests cover registration, source/target checks, paths, contract forwarding, result validation, and USD argument compatibility branches. Service doubles verify interface behavior. The separate export test creates real USDs and textures; the dependency test requires network access and installs packages only into a temporary directory.

The smoke test uses the default cube, which already has UVs; passing it does not prove UV generation works. The newer USD argument branch uses simulated RNA. Export tests cover physics schemas, geometry transforms, material bindings, portable textures and cleanup, but do not run Isaac Sim. The added metallic, roughness and alpha baking has not been runtime-validated. Use the [compatibility validation procedure](compatibility.md#validation-procedure) for GPU validation on the target equipment.

## Contribution conventions

Keep code, comments, messages, and documentation in English. Place algorithms in services, version-specific behavior in adapters, and reusable data contracts in core. Add panel settings only when the user needs control over a behavior. Document input assumptions, temporary resources, failure cleanup, and output guarantees for each implementation.

Project source is distributed under the [MIT License](../LICENSE). Keep the license notice in redistributed copies and installation packages.
