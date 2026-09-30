"""Load optional USD dependencies during export; never install binary modules automatically."""
from importlib import import_module

from ..core.errors import CompatibilityError


def require_usd(*, with_physx=False):
    """Return a module mapping; USD export support does not imply pxr is importable.

    A future implementation may use Isaac Sim Python for post-processing when
    bindings are unavailable. Do not copy system Python pxr binaries into
    Blender because their ABI may be incompatible.
    """
    names = ["Usd", "UsdGeom", "UsdShade", "UsdPhysics", "Sdf"]
    if with_physx:
        names.append("PhysxSchema")
    try:
        return {name: import_module(f"pxr.{name}") for name in names}
    except (ImportError, OSError) as exc:
        raise CompatibilityError(
            "USD/PhysX Python bindings are missing. Configure dependencies for Blender Python, "
            "or author USD physics attributes using Isaac Sim Python."
        ) from exc
