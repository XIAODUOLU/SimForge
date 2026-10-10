"""Run real Retopo -> five-channel GPU Bake -> USD Export in each target Blender.

blender -b --factory-startup --python-exit-code 1 --python tests/blender_pipeline.py
"""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy

from simforge.core.contracts import (
    BakeChannel, BakeOptions, ExportOptions, PhysicsOptions, RetopoOptions,
)
from simforge.services.bake import bake
from simforge.services.export import export
from simforge.services.retopo import retopo


source = bpy.context.active_object
source.name = 'SimForgeSource'
source_mesh = source.data
source_faces = len(source_mesh.polygons)
material = bpy.data.materials.new('SimForgeSourceMaterial')
material.use_nodes = True
principled = next(node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
for name, value in (
    ('Base Color', (.8, .2, .1, 1)), ('Metallic', .35),
    ('Roughness', .65), ('Alpha', .75),
):
    principled.inputs[name].default_value = value
source_mesh.materials.clear()
source_mesh.materials.append(material)

cycles = bpy.context.preferences.addons['cycles'].preferences
cycles.get_devices()
devices = [device for device in cycles.devices if device.type in {'OPTIX', 'CUDA'}]
assert devices, 'A Cycles GPU device is required for this runtime validation.'
for device in devices:
    device.use = True

with tempfile.TemporaryDirectory(prefix='simforge-pipeline-') as directory:
    output = Path(directory)
    low = retopo(bpy.context, source, RetopoOptions(target_faces=100, voxel_size=.1)).low_poly
    assert low is not source and low.data is not source_mesh
    assert source.data is source_mesh and len(source_mesh.polygons) == source_faces
    assert low.data.polygons and low.data.uv_layers.active

    textures = bake(bpy.context, source, low, BakeOptions(resolution=32, cage_extrusion=.03), output).textures
    assert set(textures) == set(BakeChannel)
    assert all(path.is_file() and path.stat().st_size > 100 for path in textures.values())

    destination = output / 'asset.usda'
    export(bpy.context, low, ExportOptions(destination, PhysicsOptions(mass_kg=2.5)))
    assert destination.is_file() and (output / 'asset_textures').is_dir()
    assert source.data is source_mesh and len(source_mesh.polygons) == source_faces

print('SIMFORGE_PIPELINE_OK', bpy.app.version_string)
