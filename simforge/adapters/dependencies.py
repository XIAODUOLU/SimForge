"""Install missing USD bindings with Blender's Python, into plugin user data."""
from __future__ import annotations

import importlib
import importlib.util
import platform
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy

from ..core.errors import CompatibilityError

USD_REQUIREMENT = 'usd-core>=24.5,<27'
USD_MODULES = ('Usd', 'UsdGeom', 'UsdShade', 'UsdPhysics', 'Sdf')


def _bindings_available():
    try:
        for name in USD_MODULES:
            importlib.import_module('pxr.' + name)
        return True
    except (ImportError, OSError):
        return False


def _forget_failed_imports():
    for name in tuple(sys.modules):
        if name == 'pxr' or name.startswith('pxr.'):
            del sys.modules[name]
    importlib.invalidate_caches()


def _pip_command():
    python = Path(sys.executable)
    if not python.is_file() or python.stem.lower().startswith('blender'):
        raise CompatibilityError("Cannot locate Blender's Python executable for USD installation.")
    if importlib.util.find_spec('pip') is not None:
        return [str(python), '-m', 'pip']
    # Run ensurepip's bundled pip directly. This avoids modifying the Blender
    # installation or the user's shared Python packages just to bootstrap pip.
    try:
        import ensurepip
        wheels = sorted((Path(ensurepip.__file__).parent / '_bundled').glob('pip-*.whl'))
    except ImportError:
        wheels = []
    if not wheels:
        raise CompatibilityError("Blender Python has neither pip nor ensurepip. Install pip for this interpreter first.")
    return [str(python), '-c',
            "import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); "
            "runpy.run_module('pip', run_name='__main__', alter_sys=True)", str(wheels[-1])]


def ensure_usd_dependencies():
    """Called on add-on enable; skip pip when native or cached bindings work.

    pip resolves the platform/Python ABI. Install into user data, never system
    Python or Blender's application folder. First installation needs a network
    connection; later activations reuse the cached modules.
    """
    if _bindings_available():
        return
    cache = Path(bpy.utils.user_resource('SCRIPTS', path='simforge_dependencies', create=True))
    target = cache / f'py{sys.version_info.major}{sys.version_info.minor}-{sys.platform}-{platform.machine()}'
    if target.is_dir():
        if str(target) not in sys.path:
            sys.path.insert(0, str(target))
        _forget_failed_imports()
        if _bindings_available():
            return
        raise CompatibilityError(f"Cached USD bindings cannot load. Remove {target} and re-enable SimForge.")
    command = _pip_command()
    print(f'SimForge: installing {USD_REQUIREMENT} with Blender Python into {target}', flush=True)
    try:
        with TemporaryDirectory(prefix='.usd-install-', dir=cache) as directory:
            installed = Path(directory) / 'site-packages'
            result = subprocess.run(command + [
                'install', USD_REQUIREMENT, '--target', str(installed),
                '--only-binary=:all:', '--disable-pip-version-check', '--no-input', '--no-user',
                '--timeout', '30', '--retries', '1',
            ], capture_output=True, text=True, timeout=180)
            if result.returncode:
                details = (result.stderr or result.stdout).strip()[-2000:]
                raise CompatibilityError(f'USD installation failed. Check the network and pip configuration.\n{details}')
            try:
                installed.rename(target)
            except FileExistsError:
                if not target.is_dir():
                    raise
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CompatibilityError(f'Cannot install USD with Blender Python: {exc}') from exc
    sys.path.insert(0, str(target))
    _forget_failed_imports()
    if not _bindings_available():
        raise CompatibilityError(f'Installed USD bindings cannot load in this Blender build: {target}')
