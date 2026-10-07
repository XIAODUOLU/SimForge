"""Service entry point for generating a low-poly mesh from a high-poly source."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.contracts import RetopoOptions, RetopoResult
from ..core.errors import FeatureNotImplemented

if TYPE_CHECKING:
    from bpy.types import Context, Object


def retopo(context: Context, high_poly: Object, options: RetopoOptions) -> RetopoResult:
    """Create a low-poly object; preserve the source mesh, UVs, materials and transforms.

    Args:
        context (bpy.types.Context): Blender execution context, normally bpy.context
            or the Operator's context. Supplies the scene, view layer, selection
            and active object. Call in Object Mode on Blender's main thread.
        high_poly (bpy.types.Object): Original nonempty MESH object in the current
            view layer. This is an object reference, not a Mesh datablock or file
            path. Preserve it and its mesh data as the later baking source.
        options (RetopoOptions): Immutable settings snapshot. target_faces is the
            requested face count; voxel_ratio is relative to the longest bounds
            edge; smart_uv_angle is in radians; uv_margin is UV-space spacing.
            See core.contracts.RetopoOptions for types and defaults.

    Returns:
        RetopoResult: Return RetopoResult(low_poly=new_object), where low_poly is
            a new bpy.types.Object of type MESH with independent mesh data,
            linked into the current view layer, and active, unwrapped, packed UVs.
            Return the result wrapper rather than the bare object.

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
