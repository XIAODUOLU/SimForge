"""Load USD bindings supplied by Blender or installed with Blender's pip."""
from importlib import import_module

from ..core.errors import CompatibilityError
from .dependencies import ensure_usd_dependencies


def require_usd(*, with_physx=False):
    """Return a module mapping; USD export support does not imply pxr is importable.

    Missing core bindings are installed using Blender's own Python interpreter.
    PhysxSchema is optional and requires a separate NVIDIA runtime.
    """
    names = ["Usd", "UsdGeom", "UsdShade", "UsdPhysics", "Sdf"]
    if with_physx:
        names.append("PhysxSchema")
    ensure_usd_dependencies()
    try:
        return {name: import_module(f"pxr.{name}") for name in names}
    except (ImportError, OSError) as exc:
        raise CompatibilityError(
            "Required USD bindings are missing. Re-enable SimForge to install usd-core. "
            "PhysxSchema, when requested, "
            "requires an NVIDIA runtime and is not included in usd-core."
        ) from exc
