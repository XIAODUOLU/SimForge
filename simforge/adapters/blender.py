"""Detect RNA capabilities across 4.x/5.x and report missing requirements explicitly."""
import bpy

from ..core.errors import CompatibilityError


def ensure_supported_version():
    if not (4, 0, 0) <= bpy.app.version < (6, 0, 0):
        raise CompatibilityError("SimForge targets Blender 4.x–5.x.")


def operator_properties(operator):
    """Use get_rna_type; hasattr(bpy.ops...) may return a dynamic placeholder proxy."""
    try:
        return operator.get_rna_type().properties
    except (AttributeError, RuntimeError) as exc:
        raise CompatibilityError("This Blender build lacks the required operator.") from exc


def checked_kwargs(operator, required, optional=None):
    """Never discard required arguments; omit optional arguments only when correctness is unaffected."""
    properties = operator_properties(operator)
    missing = set(required) - set(properties.keys())
    if missing:
        raise CompatibilityError("Operator is missing arguments: " + ", ".join(sorted(missing)))
    result = dict(required)
    result.update({key: value for key, value in (optional or {}).items()
                   if key in properties})
    for key, value in result.items():
        prop = properties[key]
        if prop.type == 'ENUM' and not prop.is_enum_flag:
            if value not in prop.enum_items.keys():
                raise CompatibilityError(f"Operator argument {key} does not support value {value!r}.")
    return result


def usd_export_kwargs(filepath):
    """Build arguments without exporting. The caller must isolate selection and set the active object."""
    operator = bpy.ops.wm.usd_export
    properties = operator_properties(operator)
    required = {
        "filepath": str(filepath), "selected_objects_only": True,
        "export_materials": True, "export_uvmaps": True,
        "export_normals": True, "relative_paths": True,
    }
    # Blender 5.0 removed export_textures in favor of export_textures_mode.
    if "export_textures_mode" in properties:
        required["export_textures_mode"] = "NEW"
    elif "export_textures" in properties:
        required["export_textures"] = True
    else:
        raise CompatibilityError("The current USD exporter does not support texture export.")
    return checked_kwargs(operator, required)


def principled_input(node, name):
    """Access inputs by name to avoid socket index changes between Blender versions."""
    if node.type != 'BSDF_PRINCIPLED':
        raise CompatibilityError("Expected a Principled BSDF node.")
    socket = node.inputs.get(name)
    if socket is None:
        raise CompatibilityError(f"Principled BSDF is missing input: {name}")
    return socket
