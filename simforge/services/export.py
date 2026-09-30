"""Service entry point for exporting self-contained, reusable Isaac Sim USD assets."""
from ..core.contracts import ExportOptions, ExportResult
from ..core.errors import FeatureNotImplemented


def export(context, low_poly, options: ExportOptions) -> ExportResult:
    """Write USD, relative texture paths and standard physics/collision attributes.

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
