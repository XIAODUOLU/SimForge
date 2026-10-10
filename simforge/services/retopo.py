"""Service entry point for generating a low-poly mesh from a high-poly source."""

from __future__ import annotations

from ..adapters.blender import checked_kwargs
from ..adapters.context import preserve_selection
from ..core.contracts import RetopoOptions, RetopoResult
from ..core.errors import SimForgeError

from bpy.types import Context, Object

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

    if context.mode != 'OBJECT':
        raise SimForgeError('Retopo requires Object Mode.')
    if (high_poly is None or high_poly.type != 'MESH' or not high_poly.data.polygons
            or context.view_layer.objects.get(high_poly.name) != high_poly):
        raise SimForgeError('Retopo requires a nonempty mesh in the current view layer.')

    low_poly = None
    mesh = None
    try:
        with preserve_selection(context):
            depsgraph = context.evaluated_depsgraph_get()
            evaluated = high_poly.evaluated_get(depsgraph)
            mesh = bpy.data.meshes.new_from_object(
                evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
            low_poly = high_poly.copy()
            low_poly.name = high_poly.name + 'LowPoly'
            low_poly.data = mesh
            mesh.name = high_poly.data.name + 'LowPoly'
            low_poly.modifiers.clear()
            context.collection.objects.link(low_poly)
            for obj in tuple(context.selected_objects):
                obj.select_set(False)
            low_poly.select_set(True)
            context.view_layer.objects.active = low_poly

            mesh.remesh_mode = 'VOXEL'
            mesh.remesh_voxel_size = options.voxel_size
            mesh.remesh_voxel_adaptivity = 0
            mesh.use_remesh_fix_poles = True
            mesh.use_remesh_preserve_volume = True
            if hasattr(mesh, 'use_remesh_preserve_attributes'):
                mesh.use_remesh_preserve_attributes = True
            if bpy.ops.object.voxel_remesh() != {'FINISHED'}:
                raise SimForgeError('Voxel remesh did not finish.')

            mesh.remesh_mode = 'QUAD'
            quadriflow_args = checked_kwargs(
                bpy.ops.object.quadriflow_remesh,
                {'mode': 'FACES', 'target_faces': options.target_faces},
                {'use_mesh_symmetry': True, 'use_preserve_sharp': False,
                 'use_preserve_boundary': False, 'preserve_attributes': False,
                 'smooth_normals': True, 'seed': 42})
            if bpy.ops.object.quadriflow_remesh(**quadriflow_args) != {'FINISHED'}:
                raise SimForgeError('QuadriFlow remesh did not finish.')

            bpy.ops.object.mode_set(mode='EDIT')
            try:
                bpy.ops.mesh.select_mode(type='FACE')
                bpy.ops.mesh.select_all(action='SELECT')
                if bpy.ops.uv.smart_project(
                        angle_limit=options.smart_uv_angle,
                        scale_to_bounds=True) != {'FINISHED'}:
                    raise SimForgeError('Smart UV Project did not finish.')
                if bpy.ops.uv.pack_islands(margin=options.uv_margin) != {'FINISHED'}:
                    raise SimForgeError('UV packing did not finish.')
            finally:
                bpy.ops.object.mode_set(mode='OBJECT')

            if not mesh.polygons or mesh.uv_layers.active is None:
                raise SimForgeError('Retopology produced no usable mesh or UV map.')
            mesh.materials.clear()
        return RetopoResult(low_poly)
    except Exception:
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if low_poly is not None:
            bpy.data.objects.remove(low_poly, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise
