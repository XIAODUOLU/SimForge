"""Stable contracts for the three services; object references are local to the Blender process."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from bpy.types import Object


class BakeChannel(str, Enum):
    NORMAL = "normal"
    BASE_COLOR = "base_color"  # Diffuse color only, excluding lighting and shadows.
    METALLIC = "metallic"
    ROUGHNESS = "roughness"
    ALPHA = "alpha"


@dataclass(frozen=True)
class RetopoOptions:
    """Immutable retopology settings; annotations do not validate values at runtime.

    Attributes:
        target_faces (int): Requested output face count (default 8000); QuadriFlow
            does not guarantee this exact count.
        voxel_ratio (float): Voxel size divided by the longest bounding-box edge
            (default 0.005). Use consistent coordinates; this is not a length.
        smart_uv_angle (float): Smart UV Project angle limit in radians
            (default 1.1519173063, approximately 66 degrees).
        uv_margin (float): UV-space spacing between packed islands (default 0.02).
            The implementation must explicitly define the packing margin semantics.
    """

    target_faces: int = 8000
    voxel_ratio: float = 0.005  # Fraction of the longest bounding-box edge, not a world-space length.
    smart_uv_angle: float = 1.1519173063  # Radians, approximately 66 degrees.
    uv_margin: float = 0.02  # UV-space spacing; the adapter must define its precise semantics.


@dataclass(frozen=True)
class BakeOptions:
    """Immutable texture baking settings.

    Attributes:
        resolution (int): Width and height of each square texture in pixels
            (default 2048, meaning 2048 x 2048).
        margin_pixels (int): Padding around baked UV islands in pixels (default 16).
        cage_extrusion (float): Baking projection cage extrusion distance in
            Blender scene length units (default 0.01), not automatically meters.
        channels (tuple[BakeChannel, ...]): Channels to bake; defaults to all five:
            NORMAL (tangent-space normals), BASE_COLOR (color without lighting),
            METALLIC (metalness), ROUGHNESS (roughness), ALPHA (opacity).
            Direct callers may request a subset. Use enum members, not raw strings.
    """

    resolution: int = 2048
    margin_pixels: int = 16
    cage_extrusion: float = 0.01  # Blender scene length units.
    channels: tuple[BakeChannel, ...] = tuple(BakeChannel)


@dataclass(frozen=True)
class PhysicsOptions:
    """Immutable USD physics settings used by ExportOptions.

    Attributes:
        body_type (str): 'DYNAMIC' for a rigid body with mass, or 'STATIC' for
            collision only (default 'DYNAMIC').
        mass_kg (float): Dynamic rigid-body mass in kilograms (default 1.0).
        collision_approximation (str): Collision mesh approximation; the UI offers
            'convexHull' (default) and 'convexDecomposition'. The service must
            check support for the requested approximation.
        static_friction (float): Dimensionless static friction coefficient
            (default 0.5).
        dynamic_friction (float): Dimensionless sliding friction coefficient
            (default 0.5).
        restitution (float): Dimensionless restitution coefficient, from 0 to 1
            (default 0.0; zero means no bounce).
    """

    body_type: str = "DYNAMIC"  # DYNAMIC / STATIC.
    mass_kg: float = 1.0
    collision_approximation: str = "convexHull"
    static_friction: float = 0.5
    dynamic_friction: float = 0.5
    restitution: float = 0.0


@dataclass(frozen=True)
class ExportOptions:
    """Immutable export destination, physics and coordinate conversion settings.

    Attributes:
        filepath (pathlib.Path): Absolute final output file path, ending in .usd,
            .usda or .usdc. Required; workflow rejects an existing destination.
        physics (PhysicsOptions): Required nested body/collision/material settings.
        meters_per_blender_unit (float): Meters represented by one Blender scene
            length unit (default 1.0); workflow takes scene.unit_settings.scale_length.
            Convert geometry/transforms as well as setting USD metersPerUnit=1.
    """

    filepath: Path
    physics: PhysicsOptions
    meters_per_blender_unit: float = 1.0
    # Output contract: Z-up, metersPerUnit=1; convert transforms/vertices to meters.


@dataclass(frozen=True)
class RetopoResult:
    """Retopo output: low_poly is a new bpy.types.Object of type MESH.

    Link the object into the current view layer and give it independent mesh data
    with an active, unwrapped and packed UV map. Return RetopoResult(low_poly=obj).
    """

    low_poly: Object  # A new Mesh object with an active, unwrapped and packed UV map.


@dataclass(frozen=True)
class BakeResult:
    """Bake output: textures is a Mapping[BakeChannel, pathlib.Path].

    A dict is sufficient. Each requested channel maps to its saved texture's
    absolute path. For example: BakeResult(textures={BakeChannel.NORMAL: path}).
    This example is complete only when NORMAL is the sole requested channel.
    """

    textures: Mapping[BakeChannel, Path]  # Saved files for every requested channel.


@dataclass(frozen=True)
class ExportResult:
    """Export output: filepath is the absolute pathlib.Path of the final USD.

    Return ExportResult(filepath=options.filepath) after committing and validating
    the asset, its texture resources, physics and collision schemas.
    """

    filepath: Path  # Final USD with physics and collision schemas authored.
