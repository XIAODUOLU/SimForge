"""Blender add-on entry point for converting AI assets into simulation assets."""

bl_info = {
    "name": "SimForge",
    "author": "SimForge Contributors",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > SimForge",
    "description": "Retopology, PBR baking and simulation-ready USD assets",
    "category": "Object",
}


def register():
    """Import bpy lazily so pure Python contracts and build tools can import this package."""
    from .registration import register as register_addon
    register_addon()


def unregister():
    from .registration import unregister as unregister_addon
    unregister_addon()
