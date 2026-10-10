"""Real USD integration: blender -b --factory-startup --python-exit-code 1 --python tests/blender_export.py."""
from dataclasses import replace
from pathlib import Path
import math
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade
from simforge.core.contracts import ExportOptions, PhysicsOptions
from simforge.core.errors import SimForgeError
from simforge.services import export as service
import simforge


def expect_error(callback, exception=SimForgeError):
    try:
        callback()
    except exception:
        return
    raise AssertionError(f'Expected {exception.__name__}')


def snapshot():
    return (set(bpy.data.objects), set(bpy.data.meshes), set(bpy.context.selected_objects),
            bpy.context.view_layer.objects.active, bpy.context.scene.unit_settings.scale_length)


obj = bpy.context.active_object
# Parent pose, nonuniform/negative scale, shear and a real modifier must survive
# unit conversion. None of these may remain as a scale on the rigid body root.
parent = bpy.data.objects.new('Parent', None)
bpy.context.collection.objects.link(parent)
parent.location = (4, -2, 3)
parent.rotation_euler = (.2, .3, -.4)
parent.scale = (1.2, .8, 1.6)  # Rotated child under nonuniform parent introduces shear.
obj.parent = parent
obj.location = (2, 3, 4)
obj.rotation_euler = (.3, .1, .2)
obj.scale = (-2, .5, 3)
modifier = obj.modifiers.new('Triangulate', 'TRIANGULATE')
bpy.context.scene.unit_settings.scale_length = .01
bpy.context.view_layer.update()
original_matrix = obj.matrix_world.copy()
original_points = [vertex.co.copy() for vertex in obj.data.vertices]
expected_points = [obj.matrix_world @ vertex.co * .01 for vertex in obj.data.vertices]
initial = snapshot()

with tempfile.TemporaryDirectory() as directory:
    base = Path(directory)
    # Constant materials need no image textures; exercise the .usd destination.
    constant = base / 'constant.usd'
    service.export(bpy.context, obj, ExportOptions(constant, PhysicsOptions(), .01))
    assert constant.is_file() and not (base / 'constant_textures').exists()
    assert snapshot() == initial
    second_material = obj.data.materials[0].copy()
    obj.data.materials.append(second_material)
    for face in obj.data.polygons:
        face.material_index = face.index % 2
    image = bpy.data.images.new('BakedDiffuse', width=4, height=4)
    image.filepath_raw = str(base / 'source.png')
    image.file_format = 'PNG'
    image.save()
    normal = bpy.data.images.new('BakedNormal', width=4, height=4)
    normal.colorspace_settings.name = 'Non-Color'
    normal.filepath_raw = str(base / 'normal.png')
    normal.file_format = 'PNG'
    normal.save()
    material = obj.data.materials[0]
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = next(node for node in nodes if node.type == 'BSDF_PRINCIPLED')
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = image
    links.new(texture.outputs['Color'], bsdf.inputs['Base Color'])
    normal_texture = nodes.new('ShaderNodeTexImage')
    normal_texture.image = normal
    normal_map = nodes.new('ShaderNodeNormalMap')
    links.new(normal_texture.outputs['Color'], normal_map.inputs['Color'])
    links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
    slots = tuple(obj.data.materials)
    for body_type in ('DYNAMIC', 'STATIC'):
        for approximation in ('convexHull', 'convexDecomposition'):
            target = base / '输出 with spaces' / f'{body_type}_{approximation}.usdc'
            physics = PhysicsOptions(body_type=body_type, mass_kg=2.5, collision_approximation=approximation,
                                     static_friction=.7, dynamic_friction=.4, restitution=.1)
            options = ExportOptions(target, physics, .01)
            assert service.export(bpy.context, obj, options).filepath == target
            assert snapshot() == initial
            assert obj.matrix_world == original_matrix
            assert [vertex.co for vertex in obj.data.vertices] == original_points
            assert tuple(obj.data.materials) == slots and modifier in tuple(obj.modifiers)
            stage = Usd.Stage.Open(str(target))
            root = stage.GetDefaultPrim()
            assert str(root.GetPath()) == '/Asset'
            assert UsdGeom.GetStageMetersPerUnit(stage) == 1 and UsdGeom.GetStageUpAxis(stage) == 'Z'
            assert UsdPhysics.GetStageKilogramsPerUnit(stage) == 1
            assert root.HasAPI(UsdPhysics.RigidBodyAPI) == (body_type == 'DYNAMIC')
            assert root.HasAPI(UsdPhysics.MassAPI) == (body_type == 'DYNAMIC')
            root_transform = UsdGeom.Xformable(root).GetLocalTransformation()
            assert all(math.isclose(sum(root_transform[row][col] ** 2 for col in range(3)), 1, abs_tol=1e-5) for row in range(3))
            meshes = [prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh)]
            assert len(meshes) == 1
            mesh = UsdGeom.Mesh(meshes[0])
            assert len(mesh.GetFaceVertexCountsAttr().Get()) == 12  # Modifier evaluated.
            assert UsdPhysics.MeshCollisionAPI(mesh.GetPrim()).GetApproximationAttr().Get() == approximation
            world = UsdGeom.XformCache().GetLocalToWorldTransform(mesh.GetPrim())
            actual_points = [world.Transform(point) for point in mesh.GetPointsAttr().Get()]
            for expected in expected_points:
                assert min(sum((actual[i] - expected[i]) ** 2 for i in range(3)) for actual in actual_points) < 1e-12
            visual, _ = UsdShade.MaterialBindingAPI(mesh.GetPrim()).ComputeBoundMaterial()
            physical, _ = UsdShade.MaterialBindingAPI(mesh.GetPrim()).ComputeBoundMaterial('physics')
            subsets = UsdGeom.Subset.GetAllGeomSubsets(UsdGeom.Imageable(mesh))
            assert len(subsets) == 2
            assert physical
            for subset in subsets:
                visual, _ = UsdShade.MaterialBindingAPI(subset.GetPrim()).ComputeBoundMaterial()
                inherited_physics, _ = UsdShade.MaterialBindingAPI(subset.GetPrim()).ComputeBoundMaterial('physics')
                assert visual and visual.GetPath() != physical.GetPath()
                assert inherited_physics.GetPath() == physical.GetPath()
            uv_names = {primvar.GetBaseName(): primvar for primvar in UsdGeom.PrimvarsAPI(mesh).GetPrimvars()
                        if primvar.GetAttr().Get()}
            shader_uv_names = {attr.Get() for prim in stage.Traverse() for attr in prim.GetAttributes()
                               if attr.GetName() == 'inputs:varname'}
            assert shader_uv_names and shader_uv_names <= uv_names.keys()
            assert not any(prim.GetTypeName() in {'DomeLight', 'Camera', 'PhysicsScene'} for prim in stage.Traverse())
            assert any(attr.GetName() == 'inputs:normal' and attr.GetConnections() for prim in stage.Traverse() for attr in prim.GetAttributes())
            resource_paths = [value.path for _, value in service._asset_attributes(stage, service.require_usd()['Sdf'])]
            assert len(resource_paths) == 2
            assert all((target.parent / path).is_file() for path in resource_paths)
            old = target.read_bytes()
            expect_error(lambda: service.export(bpy.context, obj, options))
            assert target.read_bytes() == old and snapshot() == initial
            # Moving the asset and its resource folder must keep both texture paths valid.
            relocated = base / ('relocated_' + target.stem)
            relocated.mkdir()
            shutil.copy2(target, relocated / target.name)
            shutil.copytree(target.parent / (target.stem + '_textures'), relocated / (target.stem + '_textures'))
            moved = Usd.Stage.Open(str(relocated / target.name))
            assert all(value.resolvedPath and Path(value.resolvedPath).is_file()
                       for _, value in service._asset_attributes(moved, service.require_usd()['Sdf']))

    options = ExportOptions(base / 'failure.usda', PhysicsOptions(), .01)
    before = set(base.iterdir())
    original_validate = service._validate_stage
    try:
        def fail_validation(*args):
            raise SimForgeError('Injected validation failure')
        service._validate_stage = fail_validation
        expect_error(lambda: service.export(bpy.context, obj, options))
    finally:
        service._validate_stage = original_validate
    assert set(base.iterdir()) == before and snapshot() == initial

    # A resource collision must preserve the unrelated folder and leave no USD.
    existing_resources = base / 'failure_textures'
    existing_resources.mkdir()
    sentinel = existing_resources / 'keep.txt'
    sentinel.write_text('keep')
    expect_error(lambda: service.export(bpy.context, obj, options))
    assert sentinel.read_text() == 'keep' and not options.filepath.exists()
    assert snapshot() == initial

    # Inject failure while publishing the USD, after publishing its textures.
    original_copy = service.shutil.copyfileobj
    try:
        def fail_copy(*args):
            raise OSError('Injected publication failure')
        service.shutil.copyfileobj = fail_copy
        publish_options = replace(options, filepath=base / 'publish.usda')
        expect_error(lambda: service.export(bpy.context, obj, publish_options))
    finally:
        service.shutil.copyfileobj = original_copy
    assert not publish_options.filepath.exists() and not (base / 'publish_textures').exists()
    assert snapshot() == initial
    for bad in (replace(options, meters_per_blender_unit=0),
                replace(options, physics=PhysicsOptions(mass_kg=-1)),
                replace(options, physics=PhysicsOptions(restitution=2))):
        expect_error(lambda: service.export(bpy.context, obj, bad))
    # The existing operator/workflow must pass panel values and scene units to
    # the real export implementation, without changes to UI or workflow code.
    simforge.register()
    try:
        settings = bpy.context.scene.simforge
        settings.low_poly = obj
        settings.export_path = str(base / 'panel.usda')
        settings.mass_kg = 3.0
        settings.static_friction = .8
        assert bpy.ops.simforge.export() == {'FINISHED'}
        panel_stage = Usd.Stage.Open(settings.export_path)
        assert UsdPhysics.MassAPI(panel_stage.GetDefaultPrim()).GetMassAttr().Get() == 3.0
        assert math.isclose(UsdPhysics.MaterialAPI(panel_stage.GetPrimAtPath('/Asset/PhysicsMaterial')).GetStaticFrictionAttr().Get(), .8, rel_tol=1e-6)
        assert snapshot() == initial
    finally:
        simforge.unregister()
    image.filepath_raw = str(base / 'missing.png')
    expect_error(lambda: service.export(bpy.context, obj, options))
    assert snapshot() == initial
print('SIMFORGE_EXPORT_OK', bpy.app.version_string)
