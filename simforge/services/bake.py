"""Service entry point for projecting PBR detail from the original high-poly source."""

from __future__ import annotations
from traceback import format_exc

from pathlib import Path

from ..core.contracts import BakeOptions, BakeResult, BakeChannel
from ..core.errors import SimForgeError

from bpy.types import Context, Object, ShaderNodeTexImage, Mesh, Scene, ViewLayer

import bpy
import os


def bake(
    context: Context,
    high_poly: Object,
    low_poly: Object,
    options: BakeOptions,
    output_directory: Path,
) -> BakeResult:
    """Bake requested channels, connect target textures and return saved files.

    Args:
        context (bpy.types.Context): Blender execution context, normally bpy.context
            or the Operator's context. Supplies scene/render settings, view layer
            and selection. Call in Object Mode on Blender's main thread.
        high_poly (bpy.types.Object): Original nonempty MESH source in the current
            view layer, with the source surface detail and materials to transfer.
            Preserve its mesh and materials; it is not a remeshed intermediate.
        low_poly (bpy.types.Object): Nonempty MESH target in the current view layer
            with usable active UVs. Must be a different object with different mesh
            data from high_poly. Its materials receive the baked textures.
        options (BakeOptions): Immutable settings snapshot. resolution
            is pixels; cage_extrusion is in scene length units;
            channels is a tuple of BakeChannel members, defaulting to pbr textures.
            See core.contracts.BakeOptions for types and defaults.
        output_directory (pathlib.Path): Absolute texture output directory,
            resolved by workflow before this call. Create it if needed. This is
            a directory path, not an image filename or Blender's // path string.

    Returns:
        BakeResult: Return BakeResult(textures=saved_textures), where
            saved_textures is a Mapping[BakeChannel, pathlib.Path], typically a
            dict. Include every options.channels member and map it to an absolute
            path of a saved, validated texture file, not a bpy.types.Image.
            Also connect the textures to the low-poly material before returning.

    Use Cycles selected-to-active baking with the original high-poly source
    selected and the low-poly target active. NORMAL uses tangent space;
    BASE_COLOR excludes direct and indirect lighting.
    METALLIC and ALPHA have no general native bake types: route their inputs
    through Emission in temporary materials and bake EMIT. ROUGHNESS can use
    its native channel. Use sRGB for BASE_COLOR and Non-Color for all data maps,
    including normals.

    Handle all source material slots. Edit material copies only, and restore
    the render engine, bake settings, visibility, selection, active object and
    temporary nodes/materials in finally blocks.
    An explicit cage must match the target topology; a double-layer Solidify
    mesh cannot be used directly as a cage. The implementation owns naming,
    overwrite policy and failure cleanup; never silently overwrite existing files.
    """

    try:
        # Ensure the mode is OBJECT
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        if not (
            isinstance(context.view_layer, ViewLayer)
            and isinstance(context.scene, Scene)
        ):
            raise SimForgeError("Bake Error: context error")

        if high_poly.name not in context.view_layer.objects:
            context.scene.collection.objects.link(high_poly)
        if low_poly.name not in context.view_layer.objects:
            context.scene.collection.objects.link(low_poly)

        if not isinstance(low_poly.data, Mesh):
            raise SimForgeError("Bake Error: LowPoly is not a Mesh")

        # Define new material
        mat = bpy.data.materials.new(name=low_poly.name + "Material")
        mat.use_nodes = True

        if not mat.node_tree:
            raise SimForgeError("Bake Error: material does not have node_tree")

        # Get nodes and links
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Clear the default nodes
        nodes.clear()

        # Add new nodes and images
        output = nodes.new(type="ShaderNodeOutputMaterial")
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
        diffuse = nodes.new(type="ShaderNodeTexImage")
        diffuse_image = bpy.data.images.new(
            low_poly.name + "Diffuse",
            width=options.resolution,
            height=options.resolution,
            alpha=True,
        )

        normal = nodes.new(type="ShaderNodeTexImage")
        normal_image = bpy.data.images.new(
            low_poly.name + "Normal",
            width=options.resolution,
            height=options.resolution,
            alpha=True,
        )
        normal_image.colorspace_settings.name = "Linear CIE-XYZ D65"
        normal_map = nodes.new(type="ShaderNodeNormalMap")

        # Setup links
        links.new(diffuse.outputs["Color"], bsdf.inputs["Base Color"])
        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
        links.new(diffuse.outputs["Color"], bsdf.inputs["Base Color"])
        links.new(normal.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

        if not isinstance(diffuse, ShaderNodeTexImage):
            raise SimForgeError("Bake Error: diffuse node is not ShaderNodeTexImage")
        if not isinstance(normal, ShaderNodeTexImage):
            raise SimForgeError("Bake Error: normal node is not ShaderNodeTexImage")

        diffuse.image = diffuse_image
        normal.image = normal_image

        if low_poly.data.materials:
            low_poly.data.materials.clear()
        else:
            low_poly.data.materials.append(mat)

        # Bake options
        if not isinstance(context.scene, Scene):
            raise SimForgeError("Bake Error: scene does not exist")

        context.scene.render.engine = "CYCLES"
        context.scene.cycles.device = "GPU"

        context.scene.render.bake.use_pass_color = True
        context.scene.render.bake.use_pass_direct = False
        context.scene.render.bake.use_pass_indirect = False

        context.scene.render.bake.use_selected_to_active = True
        context.scene.render.bake.cage_extrusion = options.cage_extrusion
        context.scene.render.bake.max_ray_distance = 0

        context.scene.render.bake.target = "IMAGE_TEXTURES"

        context.scene.render.bake.use_clear = True
        context.scene.render.bake.margin_type = "ADJACENT_FACES"
        context.scene.render.bake.margin = 16

        # Set select objects
        bpy.ops.object.select_all(action="DESELECT")

        low_poly.select_set(True)
        high_poly.select_set(True)

        context.view_layer.objects.active = low_poly

        for node in nodes:
            node.select = False
        diffuse.select = True
        nodes.active = diffuse

        # Bake Diffuse Image
        bpy.ops.object.bake(type="DIFFUSE")

        # Save Diffuse Image
        diffuse_image.filepath_raw = bpy.path.abspath(
            os.path.join(output_directory, diffuse_image.name)
        )
        diffuse_image.file_format = "PNG"
        diffuse_image.save()

        # Set select objects
        bpy.ops.object.select_all(action="DESELECT")

        low_poly.select_set(True)
        high_poly.select_set(True)

        context.view_layer.objects.active = low_poly

        for node in nodes:
            node.select = False
        normal.select = True
        nodes.active = normal

        # Bake Normal Image
        bpy.ops.object.bake(type="NORMAL")

        # Save Normal Image
        normal_image.filepath_raw = bpy.path.abspath(
            os.path.join(output_directory, normal_image.name)
        )
        normal_image.file_format = "PNG"
        normal_image.save()

        return BakeResult(
            {
                BakeChannel.BASE_COLOR: Path(diffuse_image.filepath_raw),
                BakeChannel.NORMAL: Path(normal_image.filepath_raw),
            }
        )

    except Exception as e:
        print(format_exc())
        raise SimForgeError("Bake Error") from e
