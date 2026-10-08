"""Connect UI to services, validate preconditions and update scene references only on success."""

from pathlib import Path

import bpy

from .core.contracts import BakeOptions, ExportOptions, PhysicsOptions, RetopoOptions
from .core.errors import SimForgeError
from .services import bake, export, retopo


def require_mesh(context, obj, label, *, uv=False):
    if obj is None or obj.type != "MESH" or not obj.data.polygons:
        raise SimForgeError(f"{label} must be a nonempty Mesh.")
    if context.view_layer.objects.get(obj.name) != obj:
        raise SimForgeError(f"{label} is not in the current View Layer.")
    if uv and obj.data.uv_layers.active is None:
        raise SimForgeError(
            f"{label} has no active UV map. Complete Retopo and UV unwrapping first."
        )


def resolve_path(raw):
    """Require a saved .blend for relative Blender paths to avoid an unknown output directory."""
    if not raw.strip():
        raise SimForgeError("Set an output path.")
    if raw.startswith("//") and not bpy.data.is_saved:
        raise SimForgeError(
            "Save the .blend file before using // relative paths, or choose an absolute path."
        )
    path = Path(bpy.path.abspath(raw)).expanduser()
    if not path.is_absolute():
        raise SimForgeError(
            "The output path must be absolute or use Blender's // relative notation."
        )
    return path.resolve()


def run_retopo(context):
    settings = context.scene.simforge
    high = (
        settings.high_poly if settings.high_poly is not None else context.active_object
    )
    require_mesh(context, high, "High-poly object")
    result = retopo.retopo(
        context,
        high,
        RetopoOptions(
            settings.target_faces,
            settings.voxel_size,
            settings.smart_uv_angle,
            settings.uv_margin,
        ),
    )
    require_mesh(context, result.low_poly, "Returned low-poly object", uv=True)
    if result.low_poly == high or result.low_poly.data == high.data:
        raise SimForgeError(
            "Retopo must return a separate object with independent mesh data."
        )
    settings.high_poly = high
    settings.low_poly = result.low_poly


def run_bake(context):
    settings = context.scene.simforge
    require_mesh(context, settings.high_poly, "High-poly object")
    require_mesh(context, settings.low_poly, "Low-poly object", uv=True)
    if (
        settings.high_poly == settings.low_poly
        or settings.high_poly.data == settings.low_poly.data
    ):
        raise SimForgeError("Bake source and target must have independent meshes.")
    directory = resolve_path(settings.texture_directory)
    if directory.exists() and not directory.is_dir():
        raise SimForgeError("The texture output path is not a directory.")
    options = BakeOptions(int(settings.resolution), settings.cage_extrusion)
    result = bake.bake(
        context, settings.high_poly, settings.low_poly, options, directory
    )
    for channel in result.textures:
        path = result.textures.get(channel)
        if path is None or not Path(path).is_file():
            raise SimForgeError(f"Bake did not return a saved {channel.value} texture.")


def run_export(context):
    settings = context.scene.simforge
    require_mesh(context, settings.low_poly, "Low-poly object", uv=True)
    filepath = resolve_path(settings.export_path)
    if filepath.suffix.lower() not in {".usd", ".usda", ".usdc"}:
        raise SimForgeError("The export path must end in .usd, .usda or .usdc.")
    if filepath.exists():
        raise SimForgeError("The destination file already exists. Choose a new path.")
    physics = PhysicsOptions(
        settings.body_type,
        settings.mass_kg,
        settings.collision_approximation,
        settings.static_friction,
        settings.dynamic_friction,
        settings.restitution,
    )
    result = export.export(
        context,
        settings.low_poly,
        ExportOptions(
            filepath,
            physics,
            context.scene.unit_settings.scale_length,
        ),
    )
    if Path(result.filepath).resolve() != filepath or not filepath.is_file():
        raise SimForgeError("Export did not return a USD file at the requested path.")
