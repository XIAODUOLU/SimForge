"""Service entry point for generating a low-poly mesh from a high-poly source."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.contracts import RetopoOptions, RetopoResult
from ..core.errors import SimForgeError

if TYPE_CHECKING:
    from bpy.types import Context, Object, Mesh

import bpy


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
            requested face count; voxel_size is relative to the longest bounds
            edge; smart_uv_angle is in radians; uv_margin is UV-space spacing.
            See core.contracts.RetopoOptions for types and defaults.

    Returns:
        RetopoResult: Return RetopoResult(low_poly=new_object), where low_poly is
            a new bpy.types.Object of type MESH with independent mesh data,
            linked into the current view layer, and active, unwrapped, packed UVs.
            Return the result wrapper rather than the bare object.

    Implementation sequence, defined in docs/architecture.md:
    1. Copy the source object and mesh data; voxel-remesh the copy using its
       bounding box and voxel_size.
    2. Validate manifold geometry; repair only if needed, then validate again.
    3. Run QuadriFlow with the requested face target; an exact count is not guaranteed.
    4. Run Smart UV Project and Pack Islands; return a new mesh with active UVs.

    Run all bpy operations on the main thread. Clean up temporary data on failure.
    Use adapters.context.preserve_selection to restore selection state.
    Make Manifold is an optional third-party capability, not a registration dependency.
    """

    try:
        # Ensure the mode is OBJECT
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")

        context.active_object = high_poly
        # Ensure modifiers applied
        bpy.ops.object.convert(target="MESH")
        bpy.ops.object.duplicate()

        # active_object changed by duplicate action
        low_poly = context.active_object
        low_poly.name = high_poly.name + "_low_poly"

        if isinstance(low_poly.data, Mesh):
            low_poly.data.remesh_mode = "VOXEL"
            low_poly.data.remesh_voxel_size = options.voxel_size
            low_poly.data.remesh_voxel_adaptivity = 0
            low_poly.data.use_remesh_fix_poles = True
            low_poly.data.use_remesh_preserve_volume = True
            low_poly.data.use_remesh_preserve_attributes = True
        bpy.ops.object.voxel_remesh()

        if isinstance(low_poly.data, Mesh):
            low_poly.data.remesh_mode = "QUAD"
        bpy.ops.object.quadriflow_remesh(
            use_mesh_symmetry=True,
            use_preserve_sharp=False,
            use_preserve_boundary=False,
            preserve_attributes=False,
            smooth_normals=True,
            mode="FACES",
            target_faces=options.target_faces,
            seed=42,
        )

        # Ensure the mode is Edit
        if bpy.context.mode != "EDIT":
            bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="FACE")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(
            angle_limit=options.smart_uv_angle,
            scale_to_bounds=True,
        )
        bpy.ops.uv.pack_islands(margin=options.uv_margin)

        # Ensure the mode is OBJECT
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        if isinstance(low_poly.data, Mesh):
            low_poly.data.materials.clear()

        return RetopoResult(low_poly)

    except Exception as e:
        raise SimForgeError("Retopo Error") from e
