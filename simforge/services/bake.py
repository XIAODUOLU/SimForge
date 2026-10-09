"""Project five PBR channels from the original source onto the low-poly mesh."""
from __future__ import annotations

from contextlib import contextmanager
import math
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

import bpy

from ..adapters.blender import enable_material_alpha, principled_input
from ..adapters.context import preserve_selection
from ..core.contracts import BakeChannel, BakeOptions, BakeResult
from ..core.errors import SimForgeError

from bpy.types import Context, Object


EMISSION_INPUTS = {
    BakeChannel.METALLIC: 'Metallic',
    BakeChannel.ROUGHNESS: 'Roughness',
    BakeChannel.ALPHA: 'Alpha',
}
TARGET_INPUTS = {BakeChannel.BASE_COLOR: 'Base Color', **EMISSION_INPUTS}
BAKE_SETTINGS = {
    'use_pass_color': True, 'use_pass_direct': False, 'use_pass_indirect': False,
    'use_selected_to_active': True, 'use_cage': False, 'max_ray_distance': 0.0,
    'target': 'IMAGE_TEXTURES', 'use_clear': True,
    'margin_type': 'ADJACENT_FACES', 'margin': 16,
    'normal_space': 'TANGENT', 'normal_r': 'POS_X', 'normal_g': 'POS_Y', 'normal_b': 'POS_Z',
}


def _validate(context, high_poly, low_poly, options, output_directory):
    if context.mode != 'OBJECT':
        raise SimForgeError('Bake requires Object Mode.')
    for obj, label in ((high_poly, 'High-poly'), (low_poly, 'Low-poly')):
        if obj is None or obj.type != 'MESH' or not obj.data.polygons:
            raise SimForgeError(f'{label} object must be a nonempty mesh.')
        if context.view_layer.objects.get(obj.name) != obj:
            raise SimForgeError(f'{label} object must be in the current view layer.')
    if high_poly == low_poly or high_poly.data == low_poly.data:
        raise SimForgeError('Bake source and target must have independent meshes.')
    if low_poly.data.users > 1:
        raise SimForgeError('Make the low-poly mesh single-user before baking.')
    if low_poly.data.uv_layers.active is None:
        raise SimForgeError('The low-poly mesh needs an active UV map.')
    if not isinstance(options.resolution, int) or options.resolution <= 0:
        raise SimForgeError('Texture resolution must be a positive integer.')
    if not math.isfinite(options.cage_extrusion) or options.cage_extrusion < 0:
        raise SimForgeError('Cage extrusion must be finite and nonnegative.')
    if (not options.channels or any(not isinstance(channel, BakeChannel) for channel in options.channels)
            or len(set(options.channels)) != len(options.channels)):
        raise SimForgeError('Bake channels must be a nonempty sequence of unique BakeChannel values.')
    for index in {face.material_index for face in high_poly.data.polygons}:
        if index >= len(high_poly.material_slots) or high_poly.material_slots[index].material is None:
            raise SimForgeError('Every high-poly face must have a source material.')
    directory = Path(output_directory)
    if not directory.is_absolute():
        raise SimForgeError('Bake requires an absolute texture directory.')
    stem = bpy.path.clean_name(low_poly.name) or 'asset'
    paths = {channel: directory / f'{stem}{channel.value}.png' for channel in options.channels}
    for path in paths.values():
        if path.exists():
            raise SimForgeError(f'Texture already exists; choose another output directory: {path}')
    return directory, paths


def _principled_surface(material):
    """Support one surface Principled BSDF, optionally connected through reroutes.

    Its inputs may use textures, procedural nodes or node groups. Shader mixes
    and a Principled BSDF hidden inside a shader group are deliberately rejected
    because their effective scalar inputs cannot be inferred unambiguously.
    """
    tree = material.node_tree
    output = tree.get_output_node('CYCLES')
    if output is None or not output.inputs['Surface'].is_linked:
        raise SimForgeError(f'Material {material.name!r} has no connected surface output.')
    node = output.inputs['Surface'].links[0].from_node
    seen = set()
    while node.type == 'REROUTE':
        if node.as_pointer() in seen or not node.inputs[0].is_linked:
            raise SimForgeError(f'Material {material.name!r} has an invalid surface connection.')
        seen.add(node.as_pointer())
        node = node.inputs[0].links[0].from_node
    if node.type != 'BSDF_PRINCIPLED':
        raise SimForgeError(f'Material {material.name!r} must connect one Principled BSDF to its surface output.')
    return output, node


def _source_copy(material, channel):
    temporary = material.copy()
    try:
        temporary.name = material.name + '_SimForgeBake'
        if not temporary.use_nodes:
            temporary.use_nodes = True
            _, bsdf = _principled_surface(temporary)
            for name, value in (('Base Color', material.diffuse_color), ('Metallic', material.metallic),
                                ('Roughness', material.roughness), ('Alpha', material.diffuse_color[3])):
                principled_input(bsdf, name).default_value = value
        if channel == BakeChannel.NORMAL:
            return temporary
        output, bsdf = _principled_surface(temporary)
        nodes, links = temporary.node_tree.nodes, temporary.node_tree.links
        if channel == BakeChannel.BASE_COLOR:
            # A fully metallic/transparent surface must still supply its base color.
            for name in ('Metallic', 'Alpha', 'Transmission Weight'):
                socket = principled_input(bsdf, name)
                for link in tuple(socket.links):
                    links.remove(link)
                socket.default_value = 1.0 if name == 'Alpha' else 0.0
            return temporary
        socket = principled_input(bsdf, EMISSION_INPUTS[channel])
        emission = nodes.new('ShaderNodeEmission')
        emission.name = 'SimForgeEmission'
        emission.inputs['Strength'].default_value = 1.0
        if socket.is_linked:
            # Preserve the original scalar socket's color-to-value conversion.
            scalar = nodes.new('ShaderNodeMath')
            scalar.operation = 'MULTIPLY'
            scalar.inputs[1].default_value = 1.0
            links.new(socket.links[0].from_socket, scalar.inputs[0])
            links.new(scalar.outputs[0], emission.inputs['Color'])
        else:
            value = socket.default_value
            emission.inputs['Color'].default_value = (value, value, value, 1.0)
        for link in tuple(output.inputs['Surface'].links):
            links.remove(link)
        links.new(emission.outputs['Emission'], output.inputs['Surface'])
        return temporary
    except Exception:
        bpy.data.materials.remove(temporary)
        raise


@contextmanager
def _source_materials(high_poly, channel):
    """Object-linked overrides avoid editing source mesh slots or shared materials."""
    bindings = [(index, high_poly.material_slots[index].link, high_poly.material_slots[index].material)
                for index in sorted({face.material_index for face in high_poly.data.polygons})]
    copies = {}
    try:
        for index, _, original in bindings:
            key = original.as_pointer()
            if key not in copies:
                copies[key] = _source_copy(original, channel)
            slot = high_poly.material_slots[index]
            slot.link = 'OBJECT'
            slot.material = copies[key]
        yield
    finally:
        for index, link, material in bindings:
            slot = high_poly.material_slots[index]
            slot.material = material  # Still object-linked; never mutate shared mesh slots.
            slot.link = link
        for material in copies.values():
            bpy.data.materials.remove(material)


def _target_material(low_poly, options, images):
    material = bpy.data.materials.new(low_poly.name + '_BakedMaterial')
    try:
        material.use_nodes = True
        nodes, links = material.node_tree.nodes, material.node_tree.links
        nodes.clear()
        output = nodes.new('ShaderNodeOutputMaterial')
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        textures = {}
        for channel in options.channels:
            image = bpy.data.images.new(f'{low_poly.name}_{channel.value}',
                                        width=options.resolution, height=options.resolution, alpha=True)
            images.append(image)
            image.colorspace_settings.name = 'sRGB' if channel == BakeChannel.BASE_COLOR else 'Non-Color'
            texture = nodes.new('ShaderNodeTexImage')
            texture.name = texture.label = channel.value
            texture.image = image
            textures[channel] = texture
        # Connect baked maps only after all passes finish, avoiding feedback from
        # the target's normal/alpha textures while subsequent channels are baked.
        return material, bsdf, textures
    except Exception:
        bpy.data.materials.remove(material)
        raise


def _connect_textures(material, bsdf, textures):
    nodes, links = material.node_tree.nodes, material.node_tree.links
    for channel, texture in textures.items():
        if channel == BakeChannel.NORMAL:
            normal_map = nodes.new('ShaderNodeNormalMap')
            normal_map.space = 'TANGENT'
            links.new(texture.outputs['Color'], normal_map.inputs['Color'])
            links.new(normal_map.outputs['Normal'], principled_input(bsdf, 'Normal'))
        else:
            # Scalar alpha is stored in RGB; the PNG alpha component is not the mask.
            links.new(texture.outputs['Color'], principled_input(bsdf, TARGET_INPUTS[channel]))
    if BakeChannel.ALPHA in textures:
        enable_material_alpha(material)


def bake(
    context: Context,
    high_poly: Object,
    low_poly: Object,
    options: BakeOptions,
    output_directory: Path,
) -> BakeResult:
    """Bake requested PBR maps on the main thread, using Cycles selected-to-active.

    NORMAL uses tangent-space normal baking and BASE_COLOR uses diffuse color
    without lighting. METALLIC, ROUGHNESS and ALPHA route the source Principled
    inputs through Emission nodes in temporary material copies. Constants and
    linked inputs are supported across all used source material slots.

    Defaults include all five channels; direct callers may request a subset.
    The target mesh must be single-user and have active UVs. On success its
    materials are replaced with one connected baked material. Source materials,
    selection, visibility, render and bake settings are restored. Failed runs
    restore target materials and remove only this run's images, materials/files.
    Existing texture files are never overwritten.
    """
    directory, paths = _validate(context, high_poly, low_poly, options, output_directory)
    scene = context.scene
    render_engine, device = scene.render.engine, scene.cycles.device
    bake_settings = scene.render.bake
    saved_settings = {name: getattr(bake_settings, name) for name in (*BAKE_SETTINGS, 'cage_extrusion')}
    old_materials = tuple(low_poly.data.materials)
    old_bindings = tuple((slot.link, slot.material) for slot in low_poly.material_slots)
    old_indices = tuple(face.material_index for face in low_poly.data.polygons)
    visibility = [(obj, obj.hide_render, obj.hide_viewport, obj.hide_get(view_layer=context.view_layer), obj.hide_select)
                  for obj in (high_poly, low_poly)]
    material = None
    images, published = [], []
    target_assigned = succeeded = False
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with preserve_selection(context):
            try:
                for obj, *_ in visibility:
                    obj.hide_render = obj.hide_viewport = obj.hide_select = False
                    obj.hide_set(False, view_layer=context.view_layer)
                for obj in tuple(context.selected_objects):
                    obj.select_set(False)
                high_poly.select_set(True)
                low_poly.select_set(True)
                context.view_layer.objects.active = low_poly
                if not high_poly.select_get() or not low_poly.select_get():
                    raise SimForgeError('Make both bake objects selectable in their collections.')
                scene.render.engine = 'CYCLES'
                scene.cycles.device = 'GPU'
                for name, value in BAKE_SETTINGS.items():
                    setattr(bake_settings, name, value)
                bake_settings.cage_extrusion = options.cage_extrusion
                material, bsdf, textures = _target_material(low_poly, options, images)
                target_assigned = True
                low_poly.data.materials.clear()
                low_poly.data.materials.append(material)
                low_poly.material_slots[0].link = 'DATA'
                for face in low_poly.data.polygons:
                    face.material_index = 0
                with TemporaryDirectory(prefix='.simforge-bake-', dir=directory) as temporary:
                    staging = Path(temporary)
                    for channel, texture in textures.items():
                        for node in material.node_tree.nodes:
                            node.select = False
                        texture.select = True
                        material.node_tree.nodes.active = texture
                        with _source_materials(high_poly, channel):
                            if channel == BakeChannel.NORMAL:
                                result = bpy.ops.object.bake(type='NORMAL')
                            elif channel == BakeChannel.BASE_COLOR:
                                result = bpy.ops.object.bake(type='DIFFUSE')
                            else:
                                # Blender's internal enum for emission baking.
                                result = bpy.ops.object.bake(type='EMIT')
                            if result != {'FINISHED'}:
                                raise SimForgeError(f'{channel.value} baking did not finish.')
                        image = texture.image
                        image.filepath_raw = str(staging / paths[channel].name)
                        image.file_format = 'PNG'
                        image.save()
                    _connect_textures(material, bsdf, textures)
                    for channel, texture in textures.items():
                        path = paths[channel]
                        with path.open('xb') as output:
                            published.append(path)
                            with (staging / path.name).open('rb') as source:
                                shutil.copyfileobj(source, output)
                        texture.image.filepath_raw = str(path)
                succeeded = True
            finally:
                for name, value in saved_settings.items():
                    setattr(bake_settings, name, value)
                scene.cycles.device = device
                scene.render.engine = render_engine
                if not succeeded and target_assigned:
                    low_poly.data.materials.clear()
                    for original in old_materials:
                        low_poly.data.materials.append(original)
                    for slot, (link, original) in zip(low_poly.material_slots, old_bindings):
                        slot.link = link
                        slot.material = original
                    for face, index in zip(low_poly.data.polygons, old_indices):
                        face.material_index = index
                # Selection restoration must run before restoring hide/select locks.
    except OSError as exc:
        raise SimForgeError(f'Cannot save baked textures: {exc}') from exc
    finally:
        for obj, hide_render, hide_viewport, hidden, hide_select in visibility:
            obj.hide_render, obj.hide_viewport = hide_render, hide_viewport
            obj.hide_set(hidden, view_layer=context.view_layer)
            obj.hide_select = hide_select
        if not succeeded:
            for path in published:
                path.unlink(missing_ok=True)
            if material is not None:
                bpy.data.materials.remove(material)
            for image in images:
                bpy.data.images.remove(image)
    return BakeResult(textures=paths)
