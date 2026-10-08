"""Blender integration test: blender -b --factory-startup --python-exit-code 1 --python tests/blender_smoke.py."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import simforge
from simforge import workflow
from simforge.adapters import blender as compatibility
from simforge.adapters.blender import checked_kwargs, usd_export_kwargs
from simforge.core.contracts import BakeResult, ExportResult, RetopoResult
from simforge.core.errors import CompatibilityError, SimForgeError
from simforge.services import bake, export, retopo


def expect_error(callback, exception):
    try:
        callback()
    except exception:
        return
    raise AssertionError(f'Expected {exception.__name__}')


simforge.register()
simforge.register()  # Repeated registration must not create duplicate RNA classes.
settings = bpy.context.scene.simforge
high = bpy.context.active_object
settings.high_poly = high
assert bpy.ops.simforge.retopo() == {'CANCELLED'}
assert settings.low_poly is None
expect_error(lambda: workflow.resolve_path('//unsaved.usd'), SimForgeError)
expect_error(lambda: checked_kwargs(bpy.ops.wm.usd_export, {'unknown_required': True}), CompatibilityError)
assert usd_export_kwargs('/tmp/simforge_probe.usdc')['selected_objects_only']

low = high.copy()
low.data = high.data.copy()
bpy.context.collection.objects.link(low)
if not low.data.uv_layers:
    low.data.uv_layers.new(name='UVMap')
original_retopo, original_bake, original_export = retopo.retopo, bake.bake, export.export
try:
    # Use service doubles to verify contracts; this does not test unimplemented algorithms.
    retopo.retopo = lambda context, source, options: RetopoResult(low)
    assert bpy.ops.simforge.retopo() == {'FINISHED'}
    assert settings.low_poly == low and settings.high_poly == high
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        settings.texture_directory = str(directory)
        settings.export_path = str(directory / 'asset.usda')
        assert bpy.ops.simforge.bake() == {'CANCELLED'}
        assert bpy.ops.simforge.export() == {'CANCELLED'}
        assert not list(directory.iterdir())

        def fake_bake(context, source, target, options, output):
            assert source == high and target == low
            textures = {}
            for channel in options.channels:
                path = output / f'{channel.value}.png'
                path.write_bytes(b'test contract only')
                textures[channel] = path
            return BakeResult(textures)

        def fake_export(context, target, options):
            assert target == low and options.physics.mass_kg > 0
            options.filepath.write_text('#usda 1.0\n')
            return ExportResult(options.filepath)

        bake.bake, export.export = fake_bake, fake_export
        assert bpy.ops.simforge.bake() == {'FINISHED'}
        assert bpy.ops.simforge.export() == {'FINISHED'}
        expect_error(lambda: workflow.run_export(bpy.context), SimForgeError)
        bake.bake = lambda *args: BakeResult({})
        expect_error(lambda: workflow.run_bake(bpy.context), SimForgeError)
    settings.low_poly = high
    expect_error(lambda: workflow.run_bake(bpy.context), SimForgeError)
finally:
    retopo.retopo, bake.bake, export.export = original_retopo, original_bake, original_export
    simforge.unregister()
assert not hasattr(bpy.types.Scene, 'simforge')
simforge.register()
simforge.unregister()
print('SIMFORGE_SMOKE_OK', bpy.app.version_string)

# Mock RNA to cover the 5.x argument branch; this does not replace testing in Blender 5.x.
original_properties = compatibility.operator_properties
try:
    common = {key: SimpleNamespace(type='BOOLEAN') for key in (
        'filepath', 'selected_objects_only', 'export_materials',
        'export_uvmaps', 'export_normals', 'relative_paths',
    )}
    for texture_key, texture_value in [('export_textures', True), ('export_textures_mode', 'NEW')]:
        properties = dict(common)
        properties[texture_key] = SimpleNamespace(type='BOOLEAN') if texture_key == 'export_textures' else SimpleNamespace(
            type='ENUM', is_enum_flag=False, enum_items={'NEW': None})
        compatibility.operator_properties = lambda operator: properties
        assert compatibility.usd_export_kwargs('/tmp/probe.usdc')[texture_key] == texture_value
    compatibility.operator_properties = lambda operator: common
    expect_error(lambda: compatibility.usd_export_kwargs('/tmp/probe.usdc'), CompatibilityError)
finally:
    compatibility.operator_properties = original_properties
print('SIMFORGE_COMPATIBILITY_BRANCHES_OK')
