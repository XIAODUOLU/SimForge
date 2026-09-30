"""Service entry point for projecting PBR detail from the original high-poly source."""
from pathlib import Path

from ..core.contracts import BakeOptions, BakeResult
from ..core.errors import FeatureNotImplemented


def bake(context, high_poly, low_poly, options: BakeOptions,
         output_directory: Path) -> BakeResult:
    """Bake five channels, connect textures to the low-poly material and return saved files.

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
