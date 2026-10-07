"""Service entry point for exporting self-contained, reusable Isaac Sim USD assets."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.contracts import ExportOptions, ExportResult
from ..core.errors import FeatureNotImplemented

if TYPE_CHECKING:
    from bpy.types import Context, Object


def export(context: Context, low_poly: Object, options: ExportOptions) -> ExportResult:
    """Write USD, relative texture paths and standard physics/collision attributes.

    Args:
        context (bpy.types.Context): Blender execution context, normally bpy.context
            or the Operator's context. Supplies the scene, view layer and selection.
            Call in Object Mode on Blender's main thread.
        low_poly (bpy.types.Object): Nonempty MESH object in the current view layer
            with usable active UVs and valid materials/textures. May come from
            Retopo/Bake or be an existing prepared mesh; validate its actual data.
        options (ExportOptions): Immutable settings snapshot. filepath is the
            absolute destination USD file path; physics contains PhysicsOptions;
            meters_per_blender_unit converts Blender scene lengths to meters.
            See core.contracts.ExportOptions and PhysicsOptions for field details.

    Returns:
        ExportResult: Return ExportResult(filepath=options.filepath) after the
            final .usd/.usda/.usdc file and its resources have been saved and
            validated. filepath is a pathlib.Path, not a USD stage or bpy object.
            The asset must use Z-up, metersPerUnit=1, a stable defaultPrim,
            relative texture references and authored physics/collision schemas.

    1. Validate target materials and external textures; copy resources to the output.
    2. Build version-compatible arguments with adapters.blender.usd_export_kwargs.
    3. Export temporary USD, convert to meters/Z-up and set defaultPrim and a stable root.
    4. Load USD APIs with adapters.usd.require_usd and author CollisionAPI,
       MeshCollisionAPI, physics materials and bindings in the USD layer.
       Apply RigidBodyAPI and MassAPI to the root for DYNAMIC assets;
       STATIC assets receive collision only. Detect optional PhysxSchema at
       execution time when PhysX-specific attributes are needed.
    5. Reopen and validate resources, schemas, units and defaultPrim before
       committing the final file.

    Blender custom properties and rigid_body settings are not USD Physics schemas.
    Do not add a global PhysicsScene to reusable assets by default. Dynamic objects
    default to convex hulls; concave objects may use convexDecomposition.
    Do not assume dynamic triangle meshes are supported.
    Export is not protected by Blender Undo; use temporary files and an explicit
    overwrite policy.
    """
    raise FeatureNotImplemented("Implement export() in services/export.py.")
