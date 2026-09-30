"""Service entry point for generating a low-poly mesh from a high-poly source."""
from ..core.contracts import RetopoOptions, RetopoResult
from ..core.errors import FeatureNotImplemented


def retopo(context, high_poly, options: RetopoOptions) -> RetopoResult:
    """Create a low-poly object; preserve the source mesh, UVs, materials and transforms.

    Implementation sequence, defined in docs/architecture.md:
    1. Copy the source object and mesh data; voxel-remesh the copy using its
       bounding box and voxel_ratio.
    2. Validate manifold geometry; repair only if needed, then validate again.
    3. Run QuadriFlow with the requested face target; an exact count is not guaranteed.
    4. Run Smart UV Project and Pack Islands; return a new mesh with active UVs.

    Run all bpy operations on the main thread. Clean up temporary data on failure.
    Use adapters.context.preserve_selection to restore selection state.
    Make Manifold is an optional third-party capability, not a registration dependency.
    """
    raise FeatureNotImplemented("Implement retopo() in services/retopo.py.")
