"""Real pip install into temporary user data (network required).

blender -b --factory-startup --python-exit-code 1 --python tests/blender_dependencies.py
"""
from pathlib import Path
import os
import sys
import tempfile
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bpy
from simforge.adapters import dependencies
from simforge.core.errors import CompatibilityError

# A Blender with working bindings must not invoke pip or create cache folders.
with patch.object(dependencies.subprocess, 'run', side_effect=AssertionError('pip should not run')):
    dependencies.ensure_usd_dependencies()

# The ensurepip fallback must execute its bundled pip without installing pip
# into the application's Python directory.
with patch.object(dependencies.importlib.util, 'find_spec', return_value=None):
    command = dependencies._pip_command()
result = dependencies.subprocess.run(command + ['--version'], capture_output=True, text=True)
assert result.returncode == 0 and 'pip' in result.stdout

with tempfile.TemporaryDirectory() as directory:
    directory = Path(directory)
    with patch.object(dependencies, '_bindings_available', return_value=False), \
         patch.object(bpy.utils, 'user_resource', return_value=str(directory)), \
         patch.object(dependencies.subprocess, 'run', side_effect=dependencies.subprocess.TimeoutExpired('pip', 180)):
        try:
            dependencies.ensure_usd_dependencies()
        except CompatibilityError:
            pass
        else:
            raise AssertionError('Pip timeout must report a compatibility error')
    assert not list(directory.iterdir())  # Interrupted install must not leave partial cache.
    with patch.object(dependencies, '_bindings_available', return_value=False), \
         patch.object(bpy.utils, 'user_resource', return_value=str(directory)), \
         patch.object(dependencies.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stderr='Network unavailable', stdout='')):
        try:
            dependencies.ensure_usd_dependencies()
        except CompatibilityError as exc:
            assert 'Network unavailable' in str(exc)
        else:
            raise AssertionError('Pip failure must report the cause')
    assert not list(directory.iterdir())

    # Simulate a Blender build without native pxr. This exercises actual pip and
    # binary loading in Blender; no packages are installed outside this temp dir.
    sys.path[:] = [entry for entry in sys.path if not (Path(entry) / 'pxr').is_dir()]
    dependencies._forget_failed_imports()
    with patch.object(bpy.utils, 'user_resource', return_value=str(directory)):
        dependencies.ensure_usd_dependencies()
        from pxr import Usd
        import pxr
        assert str(directory) in pxr.__file__
        print('INSTALLED_USD', Usd.GetVersion())
        with patch.object(dependencies.subprocess, 'run', side_effect=AssertionError('pip must run only once')):
            dependencies.ensure_usd_dependencies()
            # Simulate restarting Blender, so the existing cache must be discovered.
            sys.path[:] = [entry for entry in sys.path if not entry.startswith(str(directory))]
            dependencies._forget_failed_imports()
            dependencies.ensure_usd_dependencies()
        from simforge.core.contracts import ExportOptions, PhysicsOptions
        from simforge.services.export import export
        destination = directory / 'asset.usda'
        export(bpy.context, bpy.context.active_object, ExportOptions(destination, PhysicsOptions()))
        stage = Usd.Stage.Open(str(destination))
        assert stage.GetDefaultPrim()
print('SIMFORGE_PIP_USD_OK')
