"""Export a reusable, self-contained USD asset with Isaac Sim physics schemas."""
from __future__ import annotations

import math
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import bpy
from mathutils import Matrix

from ..adapters.blender import checked_kwargs, usd_export_kwargs
from ..adapters.context import preserve_selection
from ..adapters.usd import require_usd
from ..core.contracts import ExportOptions, ExportResult
from ..core.errors import SimForgeError

if TYPE_CHECKING:
    from bpy.types import Context, Object


def _validate(context, obj, options):
    destination = Path(options.filepath)
    if not destination.is_absolute() or destination.suffix.lower() not in {'.usd', '.usda', '.usdc'}:
        raise SimForgeError("Export requires an absolute .usd, .usda or .usdc path.")
    if destination.exists():
        raise SimForgeError(f"Export destination already exists: {destination}")
    if context.mode != 'OBJECT':
        raise SimForgeError("Export requires Object Mode.")
    if (obj is None or obj.type != 'MESH' or not obj.data.polygons
            or context.view_layer.objects.get(obj.name) != obj):
        raise SimForgeError("Export requires a nonempty mesh in the current view layer.")
    if obj.data.uv_layers.active is None:
        raise SimForgeError("The export mesh needs an active UV map.")
    if not math.isfinite(options.meters_per_blender_unit) or options.meters_per_blender_unit <= 0:
        raise SimForgeError("Meters per Blender unit must be finite and positive.")
    physics = options.physics
    if physics.body_type not in {'DYNAMIC', 'STATIC'}:
        raise SimForgeError("Body type must be DYNAMIC or STATIC.")
    if physics.collision_approximation not in {'convexHull', 'convexDecomposition'}:
        raise SimForgeError("Collision approximation must be convexHull or convexDecomposition.")
    if physics.body_type == 'DYNAMIC' and (not math.isfinite(physics.mass_kg) or physics.mass_kg <= 0):
        raise SimForgeError("Dynamic body mass must be finite and positive.")
    for name in ('static_friction', 'dynamic_friction', 'restitution'):
        value = getattr(physics, name)
        if not math.isfinite(value) or value < 0 or (name == 'restitution' and value > 1):
            raise SimForgeError(f"Invalid physics parameter: {name}.")
    if any(not math.isfinite(value) for row in obj.matrix_world for value in row):
        raise SimForgeError("The mesh transform contains nonfinite values.")
    if obj.matrix_world.determinant() == 0:
        raise SimForgeError("The mesh transform is singular; check object scale.")
    return destination


def _validate_materials(obj):
    """Validate evaluated material slots, including nested node groups."""
    def inspect_nodes(tree, seen):
        if tree is None or tree.as_pointer() in seen:
            return
        seen.add(tree.as_pointer())
        for node in tree.nodes:
            if node.type == 'GROUP':
                inspect_nodes(node.node_tree, seen)
            elif node.type == 'TEX_IMAGE':
                image = node.image
                if image is None:
                    if any(socket.is_linked for socket in node.outputs):
                        raise SimForgeError(f"Image texture node {node.name!r} has no image.")
                    continue
                if image.source not in {'FILE', 'GENERATED'}:
                    raise SimForgeError(f"Unsupported texture source {image.source}: {image.name}")
                if image.source == 'FILE' and not image.packed_file:
                    path = Path(bpy.path.abspath(image.filepath, library=image.library))
                    if not path.is_file():
                        raise SimForgeError(f"Texture file is missing: {path}")
    for index in {face.material_index for face in obj.data.polygons}:
        if index >= len(obj.material_slots) or obj.material_slots[index].material is None:
            raise SimForgeError("Every exported face must have a valid material.")
        inspect_nodes(obj.material_slots[index].material.node_tree, set())


def _asset_attributes(stage, Sdf):
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            if attr.GetTypeName() == Sdf.ValueTypeNames.Asset:
                value = attr.Get()
                if value and value.path:
                    yield attr, value
            elif attr.GetTypeName() == Sdf.ValueTypeNames.AssetArray:
                raise SimForgeError("USD asset arrays are not supported by this export.")


def _author_physics(stage, modules, options):
    Usd, UsdGeom, UsdShade, UsdPhysics = (modules[name] for name in ('Usd', 'UsdGeom', 'UsdShade', 'UsdPhysics'))
    root = stage.GetPrimAtPath('/Asset')
    if not root or root.GetTypeName() != 'Xform':
        raise SimForgeError("Blender did not export the expected /Asset root.")
    stage.SetDefaultPrim(root)
    Usd.ModelAPI(root).SetKind('component')
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1.0)
    scale = options.meters_per_blender_unit
    meshes = [UsdGeom.Mesh(prim) for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh)]
    if len(meshes) != 1:
        raise SimForgeError("Expected exactly one evaluated mesh in the exported asset.")
    # Bake scale/shear into the evaluated geometry in Blender, then put the pose on
    # the rigid body root. This avoids scaled rigid actors and double unit conversion.
    mesh = meshes[0]
    pose = mesh.GetPrim().GetParent()
    if pose.GetParent() != root:
        raise SimForgeError("Unexpected USD mesh hierarchy.")
    transform = UsdGeom.Xformable(pose).GetLocalTransformation()
    translation = transform.ExtractTranslation() * scale
    transform.SetTranslateOnly(translation)
    UsdGeom.Xformable(root).MakeMatrixXform().Set(transform)
    UsdGeom.Xformable(pose).ClearXformOpOrder()
    for attr in (mesh.GetPointsAttr(), mesh.GetExtentAttr()):
        values = attr.Get()
        if values is not None:
            attr.Set([value * scale for value in values])
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim()).CreateCollisionEnabledAttr(True)
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr(options.physics.collision_approximation)
    if options.physics.body_type == 'DYNAMIC':
        body = UsdPhysics.RigidBodyAPI.Apply(root)
        body.CreateRigidBodyEnabledAttr(True)
        body.CreateKinematicEnabledAttr(False)
        UsdPhysics.MassAPI.Apply(root).CreateMassAttr(options.physics.mass_kg)
        # Center of mass and inertia remain unauthored: Isaac Sim computes them
        # from the cooked collider and the supplied mass.
    material = UsdShade.Material.Define(stage, '/Asset/PhysicsMaterial')
    physics_material = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    physics_material.CreateStaticFrictionAttr(options.physics.static_friction)
    physics_material.CreateDynamicFrictionAttr(options.physics.dynamic_friction)
    physics_material.CreateRestitutionAttr(options.physics.restitution)
    # Use a uniform physics material for every face subset, with a separate
    # purpose so existing visual bindings continue to resolve independently.
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(
        material, bindingStrength=UsdShade.Tokens.strongerThanDescendants, materialPurpose='physics')


def _prepare_resources(stage, modules, staging, resource_name):
    """Give each asset its own texture folder; retain only contained relative paths."""
    texture_dir = staging / 'textures'
    resources = staging / resource_name
    if texture_dir.exists():
        texture_dir.rename(resources)
    for attr, value in _asset_attributes(stage, modules['Sdf']):
        path = Path(value.path)
        if path.is_absolute() or '..' in path.parts:
            raise SimForgeError(f"USD contains a nonportable resource path: {value.path}")
        parts = path.parts
        if parts and parts[0] == 'textures':
            path = Path(resource_name, *parts[1:])
        if not (staging / path).is_file():
            raise SimForgeError(f"Exported USD resource is missing: {path}")
        attr.Set(modules['Sdf'].AssetPath('./' + path.as_posix()))
    return resources if resources.exists() else None


def _validate_stage(filepath, modules, options):
    Usd, UsdGeom, UsdShade, UsdPhysics = (modules[name] for name in ('Usd', 'UsdGeom', 'UsdShade', 'UsdPhysics'))
    stage = Usd.Stage.Open(str(filepath))
    if stage is None:
        raise SimForgeError("Cannot reopen exported USD.")
    root = stage.GetDefaultPrim()
    if (not root or str(root.GetPath()) != '/Asset'
            or UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.z
            or UsdGeom.GetStageMetersPerUnit(stage) != 1.0
            or UsdPhysics.GetStageKilogramsPerUnit(stage) != 1.0):
        raise SimForgeError("Exported USD has invalid root or units.")
    dynamic = options.physics.body_type == 'DYNAMIC'
    if root.HasAPI(UsdPhysics.RigidBodyAPI) != dynamic or root.HasAPI(UsdPhysics.MassAPI) != dynamic:
        raise SimForgeError("Exported USD has incorrect rigid body schemas.")
    if dynamic and not math.isclose(UsdPhysics.MassAPI(root).GetMassAttr().Get(), options.physics.mass_kg, rel_tol=1e-6):
        raise SimForgeError("Exported USD mass differs from the requested value.")
    if dynamic and (not UsdPhysics.RigidBodyAPI(root).GetRigidBodyEnabledAttr().Get()
                    or UsdPhysics.RigidBodyAPI(root).GetKinematicEnabledAttr().Get()):
        raise SimForgeError("Exported USD does not contain an enabled dynamic rigid body.")
    meshes = [prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh)]
    if len(meshes) != 1 or not UsdGeom.Mesh(meshes[0]).GetPointsAttr().Get():
        raise SimForgeError("Exported USD has no usable mesh.")
    collider = meshes[0]
    if (not collider.HasAPI(UsdPhysics.CollisionAPI)
            or not UsdPhysics.CollisionAPI(collider).GetCollisionEnabledAttr().Get()
            or UsdPhysics.MeshCollisionAPI(collider).GetApproximationAttr().Get() != options.physics.collision_approximation):
        raise SimForgeError("Exported USD has incorrect collision properties.")
    material, _ = UsdShade.MaterialBindingAPI(collider).ComputeBoundMaterial('physics')
    if not material or not material.GetPrim().HasAPI(UsdPhysics.MaterialAPI):
        raise SimForgeError("Exported USD has no bound physics material.")
    physics_material = UsdPhysics.MaterialAPI(material.GetPrim())
    for getter, value in ((physics_material.GetStaticFrictionAttr, options.physics.static_friction),
                          (physics_material.GetDynamicFrictionAttr, options.physics.dynamic_friction),
                          (physics_material.GetRestitutionAttr, options.physics.restitution)):
        if not math.isclose(getter().Get(), value, rel_tol=1e-6, abs_tol=1e-7):
            raise SimForgeError("Exported USD physics material differs from requested values.")
    visual_materials = []
    subsets = UsdGeom.Subset.GetAllGeomSubsets(UsdGeom.Imageable(collider))
    for renderable in (collider, *(subset.GetPrim() for subset in subsets)):
        bound_physics, _ = UsdShade.MaterialBindingAPI(renderable).ComputeBoundMaterial('physics')
        if not bound_physics or bound_physics.GetPath() != material.GetPath():
            raise SimForgeError("An exported face group does not resolve the requested physics material.")
        visual, _ = UsdShade.MaterialBindingAPI(renderable).ComputeBoundMaterial()
        if visual:
            if not visual.GetSurfaceOutput().HasConnectedSource():
                raise SimForgeError("Exported visual material has no usable surface shader.")
            visual_materials.append(visual)
    if not visual_materials:
        raise SimForgeError("Exported USD has no bound visual material.")
    if any(prim.IsA(UsdPhysics.Scene) for prim in stage.Traverse()):
        raise SimForgeError("Reusable assets must not contain a global physics scene.")
    for _, value in _asset_attributes(stage, modules['Sdf']):
        path = Path(value.path)
        if path.is_absolute() or '..' in path.parts or not (filepath.parent / path).is_file():
            raise SimForgeError(f"Exported USD resource is not portable: {value.path}")
    return stage


def export(context: Context, low_poly: Object, options: ExportOptions) -> ExportResult:
    """Export only the evaluated low-poly mesh, preserving the Blender scene.

    Dynamic assets receive a rigid body and mass on /Asset. Static assets have
    collision only. Both use a separate physics material binding, preserving PBR
    render materials. Existing destination files and resource folders are never
    overwritten. Convex decomposition is cooked by Isaac Sim when loading.
    """
    destination = _validate(context, low_poly, options)
    modules = require_usd()
    resource_name = destination.stem + '_textures'
    published_file = False
    published_resources = False
    resource_target = destination.parent / resource_name
    temp_mesh = temp_obj = None
    units = context.scene.unit_settings.scale_length
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix='.simforge-export-', dir=destination.parent) as directory:
            staging = Path(directory)
            staged_file = staging / destination.name
            with preserve_selection(context):
                try:
                    depsgraph = context.evaluated_depsgraph_get()
                    evaluated = low_poly.evaluated_get(depsgraph)
                    temp_mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
                    if not temp_mesh.polygons or not temp_mesh.uv_layers.active:
                        raise SimForgeError("Evaluated mesh has no faces or active UV map.")
                    if any(not math.isfinite(value) for vertex in temp_mesh.vertices for value in vertex.co):
                        raise SimForgeError("Evaluated mesh contains nonfinite coordinates.")
                    temp_obj = bpy.data.objects.new('SimForgeGeometry', temp_mesh)
                    context.scene.collection.objects.link(temp_obj)
                    for index, slot in enumerate(low_poly.material_slots):
                        if index < len(temp_obj.material_slots):
                            temp_obj.material_slots[index].material = slot.material
                    _validate_materials(temp_obj)
                    location, rotation, _ = low_poly.matrix_world.decompose()
                    rigid = Matrix.Translation(location) @ rotation.to_matrix().to_4x4()
                    residual = rigid.inverted() @ low_poly.matrix_world
                    temp_mesh.transform(residual)
                    if residual.determinant() < 0:
                        temp_mesh.flip_normals()
                    temp_mesh.update()
                    temp_obj.matrix_world = rigid
                    for obj in tuple(context.selected_objects):
                        obj.select_set(False)
                    temp_obj.select_set(True)
                    context.view_layer.objects.active = temp_obj
                    context.scene.unit_settings.scale_length = 1.0
                    kwargs = usd_export_kwargs(staged_file)
                    kwargs.update(checked_kwargs(bpy.ops.wm.usd_export, {'root_prim_path': '/Asset'}, {
                        'export_animation': False, 'export_lights': False, 'export_cameras': False,
                        'convert_world_material': False, 'export_custom_properties': False,
                        'export_armatures': False, 'export_shapekeys': False, 'export_curves': False,
                        'export_volumes': False, 'export_hair': False, 'visible_objects_only': False,
                        'generate_preview_surface': True, 'generate_materialx_network': False,
                        'convert_orientation': False, 'overwrite_textures': False,
                    }))
                    if bpy.ops.wm.usd_export(**kwargs) != {'FINISHED'} or not staged_file.is_file():
                        raise SimForgeError("Blender USD export did not finish.")
                finally:
                    context.scene.unit_settings.scale_length = units
                    if temp_obj is not None:
                        bpy.data.objects.remove(temp_obj, do_unlink=True)
                        temp_obj = None
                    if temp_mesh is not None:
                        bpy.data.meshes.remove(temp_mesh)
                        temp_mesh = None
            stage = modules['Usd'].Stage.Open(str(staged_file))
            if stage is None:
                raise SimForgeError("Cannot open Blender's exported USD.")
            _author_physics(stage, modules, options)
            resources = _prepare_resources(stage, modules, staging, resource_name)
            stage.GetRootLayer().Save()
            stage = None
            validated_stage = _validate_stage(staged_file, modules, options)
            validated_stage = None
            if resources is not None:
                resource_target.mkdir()  # Reserve exclusively; never merge into existing resources.
                published_resources = True
                for path in resources.iterdir():
                    shutil.move(str(path), str(resource_target / path.name))
            with destination.open('xb') as output:
                published_file = True
                with staged_file.open('rb') as source:
                    shutil.copyfileobj(source, output)
        return ExportResult(filepath=destination)
    except Exception as exc:
        if published_file:
            destination.unlink(missing_ok=True)
        if published_resources:
            shutil.rmtree(resource_target)
        if isinstance(exc, OSError):
            raise SimForgeError(f"Cannot save USD asset: {exc}") from exc
        raise
