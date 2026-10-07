"""Service entry point for projecting PBR detail from the original high-poly source."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..core.contracts import BakeOptions, BakeResult
from ..core.errors import FeatureNotImplemented

if TYPE_CHECKING:
    from bpy.types import Context, Object


def bake(context: Context, high_poly: Object, low_poly: Object, options: BakeOptions,
         output_directory: Path) -> BakeResult:
    """Bake requested channels, connect target textures and return saved files.

    Args:
        context (bpy.types.Context): Blender execution context, normally bpy.context
            or the Operator's context. Supplies scene/render settings, view layer
            and selection. Call in Object Mode on Blender's main thread.
        high_poly (bpy.types.Object): Original nonempty MESH source in the current
            view layer, with the source surface detail and materials to transfer.
            Preserve its mesh and materials; it is not a remeshed intermediate.
        low_poly (bpy.types.Object): Nonempty MESH target in the current view layer
            with usable active UVs. Must be a different object with different mesh
            data from high_poly. Its materials receive the baked textures.
        options (BakeOptions): Immutable settings snapshot. resolution and
            margin_pixels are pixels; cage_extrusion is in scene length units;
            channels is a tuple of BakeChannel members, defaulting to all five.
            See core.contracts.BakeOptions for types and defaults.
        output_directory (pathlib.Path): Absolute texture output directory,
            resolved by workflow before this call. Create it if needed. This is
            a directory path, not an image filename or Blender's // path string.

    Returns:
        BakeResult: Return BakeResult(textures=saved_textures), where
            saved_textures is a Mapping[BakeChannel, pathlib.Path], typically a
            dict. Include every options.channels member and map it to an absolute
            path of a saved, validated texture file, not a bpy.types.Image.
            Also connect the textures to the low-poly material before returning.

    Use Cycles selected-to-active baking with the original high-poly source
    selected and the low-poly target active. NORMAL uses tangent space;
    BASE_COLOR excludes direct and indirect lighting.
    METALLIC and ALPHA have no general native bake types: route their inputs
    through Emission in temporary materials and bake EMIT. ROUGHNESS can use
    its native channel. Use sRGB for BASE_COLOR and Non-Color for all data maps,
    including normals.

    Handle all source material slots. Edit material copies only, and restore
    the render engine, bake settings, visibility, selection, active object and
    temporary nodes/materials in finally blocks.
    An explicit cage must match the target topology; a double-layer Solidify
    mesh cannot be used directly as a cage. The implementation owns naming,
    overwrite policy and failure cleanup; never silently overwrite existing files.
    """
    raise FeatureNotImplemented("Implement bake() in services/bake.py.")
