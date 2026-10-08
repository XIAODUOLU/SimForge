# Architecture and implementation contracts

This document defines the processing contracts for SimForge. See the [development guide](development.md) for implementation examples and [compatibility guide](compatibility.md) for version-specific boundaries.

## Dependency direction

```text
simforge/
├── __init__.py             Add-on metadata and lazy registration entry points
├── blender_manifest.toml   Blender 4.2+ Extension metadata
├── registration.py         Registration order, failure rollback and reverse cleanup
├── properties.py           Scene.simforge settings and object references
├── ui.py                   Sidebar displaying settings and triggering Operators
├── operators.py            Object Mode gate, shared reporting and logging
├── workflow.py             Parameter snapshots, preconditions and result checks
├── core/
│   ├── contracts.py        Immutable options/results without a bpy dependency
│   └── errors.py           User, compatibility and unimplemented-feature errors
├── services/
│   ├── retopo.py           New target mesh + Smart UV + Pack Islands
│   ├── bake.py             PBR baking, saving and material connections
│   └── export.py           USD output with physics and collision schemas
└── adapters/
    ├── blender.py          RNA detection, USD arguments and material input access
    ├── context.py          Selection and active-object restoration helper
    └── usd.py              Lazy loading of USD/PhysX Python bindings
scripts/build.py           Two ZIP installation formats
tests/blender_smoke.py     Integration tests inside Blender
```

Call direction: UI → Operator → Workflow → Service → Adapter. Every layer may reference core. Core does not import Blender; services do not reference UI/Operators; adapters do not depend on services. The current scope does not require a registry or dynamic algorithm plugin system.

## Data and state

`Scene.simforge` stores settings and high/low-poly PointerProperty references in the `.blend` file. Each execution creates dataclass snapshots from these properties; services do not read panel settings directly. Each scene currently maintains one source/target pair. A future CollectionProperty can support batch assets without introducing a batch state machine now.

There are no persistent "baked/exported" flags: users may edit meshes, UVs or files externally. Export may accept an existing valid low-poly mesh and PBR material, so it does not require clicking Bake first. The export implementation must inspect actual materials and textures.

Result objects do not automatically serialize Blender objects. Workflow updates source/target references only after Retopo succeeds. Bake checks that each requested channel has a file; Export checks the returned path and file existence. **These boundary checks do not replace content and quality validation inside services.**

## Retopo contract

The retopology service follows this conditional sequence:

```text
Copy source → Voxel Remesh → Validate mesh
                                 ├─ Pass → QuadriFlow → Smart UV Project → Pack Islands
                                 └─ Fail → Repair → Validate again
                                                       ├─ Pass → QuadriFlow
                                                       └─ Fail → Report error and stop
```

Derive voxel size from the `voxel_size` (default 0.005). Repair is conditional: a mesh that passes validation does not need an additional repair operation. Stop before QuadriFlow if repair cannot satisfy the mesh checks. The target face count is a request, not a guarantee of an exact output count.

Preserve the source object, Mesh, UVs, vertex colors and materials. Copy the Mesh data as well as the object to avoid changing the source. The high-poly reference must continue to point to the original textured source; do not substitute the voxelized intermediate as the baking source. Watertightness is a project quality gate. Validation should include degenerate faces and abnormal geometry, not just edge counts.

Smart UV uses radians. Specify Pack Islands margin semantics explicitly in the adapter and check support through RNA. `uv_margin` represents UV-space spacing; do not reuse values indiscriminately across different `margin_method` modes. Operator calls must explicitly manage mode, active object and selection. 3D Print Toolbox is not a guaranteed cross-version dependency. Implement repair with bmesh or detect an optional tool at execution time and report failures.

## Bake contract

| Channel | Meaning | Color space | Suggested approach |
| --- | --- | --- | --- |
| NORMAL | Tangent-space normals | Non-Color | NORMAL, with the target active |
| BASE_COLOR | Diffuse/base color without lighting | sRGB | DIFFUSE, Color only |
| METALLIC | Metallic scalar | Non-Color | EMIT through a temporary material |
| ROUGHNESS | Roughness scalar | Non-Color | ROUGHNESS or temporary EMIT |
| ALPHA | Opacity scalar | Non-Color | EMIT through a temporary material |

Handle constant values when source materials have no textures, and cover all material slots. Complex node graphs may not reduce to one Principled BSDF. Define the supported graph scope and report unsupported graphs explicitly. Do not assume `METALLIC` or `ALPHA` bake types exist.

The service creates output directories, manages the active Image Texture for every material slot, saves pbr maps and connects the target material. Restore engine changes, temporary materials, ray settings and visibility using `try/finally`. An explicit cage must satisfy target topology constraints; do not use a double-layer Solidify mesh directly as a cage.

## USD and Isaac Sim contract

Suggested reusable asset structure:

```text
asset.usdc                  defaultPrim=/Asset, Z-up, metersPerUnit=1
textures/                   Textures referenced by relative paths
/Asset                      Xform; RigidBodyAPI + MassAPI for dynamic objects
/Asset/Geometry/Mesh         Visible mesh and material bindings
/Asset/Collision/...         CollisionAPI + MeshCollisionAPI
/Asset/Looks/...             UsdPreviewSurface, physics materials and bindings
```

Quality checks must verify texture resolution after relocation, correct mesh dimensions, no duplicate transform conversion, a stable root prim and correct physics material bindings. `meters_per_blender_unit` comes from scene units. Convert coordinates/transforms to meters; changing USD unit metadata alone is insufficient.

Dynamic assets default to convex hulls, with optional convex decomposition, and take mass in kilograms. Static assets have collision without a dynamic rigid body. Physics materials include static/dynamic friction and restitution. Author standard attributes through `UsdPhysics`; load `PhysxSchema` only when PhysX-specific features are required. Exporting Blender custom properties does not author physics schemas, and Blender rigid_body settings must not be assumed to map automatically to USD physics.

Standalone assets generally should not include a global PhysicsScene; the consuming simulation scene configures it. Validate collisions, falling, contact and material loading in the target Isaac Sim version. The scaffold does not claim to generate SimReady assets yet.

## Errors and transactions

- Raise `SimForgeError` for expected errors and `CompatibilityError` for missing dependencies. Log full tracebacks for unexpected errors.
- Placeholder entry points raise `FeatureNotImplemented`; the UI returns `CANCELLED`.
- Retopo/Bake declare Undo for successful scene changes. Neither `CANCELLED` nor Undo automatically rolls back every side effect; services must clean up failed output. File writes cannot be undone.
- Export currently rejects existing destinations. Implementations must also prevent races where another process creates the target after validation, and define a texture overwrite policy.
- Prefer temporary directories/files, validate before committing, and clean up only resources created by the current operation on failure.
- `preserve_selection` restores selection and the active object only; it is not a full scene transaction. Callers must exit in Object Mode and preserve original inputs.
- Run Blender API calls on the main thread. Long operations may later use modal Operators; do not manipulate bpy in a thread pool.
