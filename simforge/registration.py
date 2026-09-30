"""Manage registration order, roll back failures and support disabling and re-enabling."""
import bpy

from .adapters.blender import ensure_supported_version
from .operators import SIMFORGE_OT_bake, SIMFORGE_OT_export, SIMFORGE_OT_retopo
from .properties import SIMFORGE_PG_settings
from .ui import SIMFORGE_PT_main

CLASSES = (
    SIMFORGE_PG_settings,
    SIMFORGE_OT_retopo, SIMFORGE_OT_bake, SIMFORGE_OT_export,
    SIMFORGE_PT_main,
)
_registered_classes = []


def register():
    ensure_supported_version()
    if _registered_classes:
        return
    try:
        for cls in CLASSES:
            bpy.utils.register_class(cls)
            _registered_classes.append(cls)
        bpy.types.Scene.simforge = bpy.props.PointerProperty(type=SIMFORGE_PG_settings)
    except Exception:
        unregister()
        raise


def unregister():
    if hasattr(bpy.types.Scene, "simforge"):
        del bpy.types.Scene.simforge
    for cls in reversed(_registered_classes):
        bpy.utils.unregister_class(cls)
    _registered_classes.clear()
