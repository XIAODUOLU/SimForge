"""Generate the four USD physics fixtures consumed by isaac_assets.py.

blender -b --factory-startup --python-exit-code 1 --python tests/blender_isaac_fixtures.py -- /path/to/output
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy

from simforge.core.contracts import ExportOptions, PhysicsOptions
from simforge.services.export import export


if '--' not in sys.argv or len(sys.argv) != sys.argv.index('--') + 2:
    raise SystemExit('Usage: blender ... --python tests/blender_isaac_fixtures.py -- OUTPUT_DIRECTORY')
output = Path(sys.argv[-1]).resolve()
output.mkdir(parents=True, exist_ok=True)
mesh = bpy.context.active_object
material = bpy.data.materials.new('SimForgeVisual')
material.use_nodes = True
mesh.data.materials.clear()
mesh.data.materials.append(material)

for body_type in ('DYNAMIC', 'STATIC'):
    for approximation in ('convexHull', 'convexDecomposition'):
        destination = output / f'{body_type}_{approximation}.usda'
        export(bpy.context, mesh, ExportOptions(destination, PhysicsOptions(
            body_type=body_type, mass_kg=2.5, collision_approximation=approximation,
            static_friction=.7, dynamic_friction=.4, restitution=.1)))
        print('SIMFORGE_FIXTURE_OK', destination)
