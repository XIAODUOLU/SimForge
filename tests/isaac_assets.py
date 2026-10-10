"""Validate SimForge USD fixtures inside Isaac Sim, including actual contact.

Run with Isaac Sim's python.sh after generating fixtures in both Blender versions:
python.sh tests/isaac_assets.py /path/to/fixture-directory
"""
from pathlib import Path
import sys

from isaacsim import SimulationApp


if len(sys.argv) < 2:
    raise SystemExit('Usage: python.sh tests/isaac_assets.py FIXTURE_DIRECTORY')
directory = Path(sys.argv[1]).resolve()
app = SimulationApp({'headless': True, 'renderer': 'RayTracedLighting', 'sync_loads': True})

import omni.usd
from pxr import Gf, Usd, UsdGeom, UsdPhysics, UsdShade
from isaacsim.core.experimental.prims import RigidPrim
from isaacsim.core.experimental.utils import app as app_utils
from isaacsim.core.experimental.utils import stage as stage_utils
from isaacsim.core.simulation_manager import SimulationManager


def open_stage(path):
    stage_utils.open_stage(str(path))
    while stage_utils.is_stage_loading():
        app.update()
    return omni.usd.get_context().get_stage()


for body_type in ('DYNAMIC', 'STATIC'):
    for approximation in ('convexHull', 'convexDecomposition'):
        path = directory / f'{body_type}_{approximation}.usda'
        assert path.is_file(), path
        stage = open_stage(path)
        root = stage.GetDefaultPrim()
        assert root and str(root.GetPath()) == '/Asset'
        assert UsdGeom.GetStageMetersPerUnit(stage) == 1
        assert UsdPhysics.GetStageKilogramsPerUnit(stage) == 1
        assert UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.z
        dynamic = body_type == 'DYNAMIC'
        assert root.HasAPI(UsdPhysics.RigidBodyAPI) == dynamic
        assert root.HasAPI(UsdPhysics.MassAPI) == dynamic
        if dynamic:
            assert abs(UsdPhysics.MassAPI(root).GetMassAttr().Get() - 2.5) < 1e-6
        meshes = [prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh)]
        assert len(meshes) == 1
        mesh = meshes[0]
        assert UsdPhysics.CollisionAPI(mesh).GetCollisionEnabledAttr().Get()
        assert UsdPhysics.MeshCollisionAPI(mesh).GetApproximationAttr().Get() == approximation
        physical, _ = UsdShade.MaterialBindingAPI(mesh).ComputeBoundMaterial('physics')
        visual, _ = UsdShade.MaterialBindingAPI(mesh).ComputeBoundMaterial()
        assert physical and visual and physical.GetPath() != visual.GetPath()
        material = UsdPhysics.MaterialAPI(physical.GetPrim())
        for attr, expected in (
            (material.GetStaticFrictionAttr(), .7),
            (material.GetDynamicFrictionAttr(), .4),
            (material.GetRestitutionAttr(), .1),
        ):
            assert abs(attr.Get() - expected) < 1e-6
        assert not any(prim.IsA(UsdPhysics.Scene) for prim in stage.Traverse())

        scene = UsdPhysics.Scene.Define(stage, '/PhysicsScene')
        scene.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
        scene.CreateGravityMagnitudeAttr(9.81)
        SimulationManager.setup_simulation(dt=1 / 60, device='cpu')
        app_utils.play()
        for _ in range(10):
            app.update()
        if dynamic:
            actor = RigidPrim('/Asset')
            mass = float(actor.get_masses().numpy().flat[0])
            start = float(actor.get_world_poses()[0].numpy()[0, 2])
            for _ in range(90):
                app.update()
            end = float(actor.get_world_poses()[0].numpy()[0, 2])
            assert abs(mass - 2.5) < .01 and end < start - .05
            print('SIMFORGE_ISAAC_DYNAMIC_OK', path.name, mass, start, end, flush=True)
        else:
            assert not root.HasAPI(UsdPhysics.RigidBodyAPI)
            print('SIMFORGE_ISAAC_STATIC_OK', path.name, flush=True)
        app_utils.stop()

for approximation in ('convexHull', 'convexDecomposition'):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1)
    stage.SetStartTimeCode(0)
    stage.SetEndTimeCode(300)
    world = UsdGeom.Xform.Define(stage, '/World')
    stage.SetDefaultPrim(world.GetPrim())
    for name, z, body in (('Platform', -1, 'STATIC'), ('Drop', 3, 'DYNAMIC')):
        parent = UsdGeom.Xform.Define(stage, f'/World/{name}')
        parent.AddTranslateOp().Set(Gf.Vec3d(0, 0, z))
        parent.GetPrim().GetReferences().AddReference(str(directory / f'{body}_{approximation}.usda'))
    scene = UsdPhysics.Scene.Define(stage, '/World/PhysicsScene')
    scene.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
    scene.CreateGravityMagnitudeAttr(9.81)
    scene_path = directory / f'contact_{approximation}.usda'
    stage.GetRootLayer().Export(str(scene_path))
    open_stage(scene_path)
    SimulationManager.setup_simulation(dt=1 / 60, device='cpu')
    app_utils.play()
    for _ in range(190):
        app.update()
    position = float(RigidPrim('/World/Drop').get_world_poses()[0].numpy()[0, 2])
    assert .8 < position < 1.25, (approximation, position)
    print('SIMFORGE_ISAAC_CONTACT_OK', approximation, position, flush=True)
    app_utils.stop()

print('SIMFORGE_ISAAC_ASSETS_OK', flush=True)
app.close()
