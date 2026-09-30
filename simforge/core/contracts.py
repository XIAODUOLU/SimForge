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
    target_faces: int = 8000
    voxel_ratio: float = 0.005  # Fraction of the longest bounding-box edge, not a world-space length.
    smart_uv_angle: float = 1.1519173063  # Radians, approximately 66 degrees.
    uv_margin: float = 0.02  # UV-space spacing; the adapter must define its precise semantics.


@dataclass(frozen=True)
class BakeOptions:
    resolution: int = 2048
    margin_pixels: int = 16
    cage_extrusion: float = 0.01  # Blender scene length units.
    channels: tuple[BakeChannel, ...] = tuple(BakeChannel)


@dataclass(frozen=True)
class PhysicsOptions:
    body_type: str = "DYNAMIC"  # DYNAMIC / STATIC.
    mass_kg: float = 1.0
    collision_approximation: str = "convexHull"
    static_friction: float = 0.5
    dynamic_friction: float = 0.5
    restitution: float = 0.0


@dataclass(frozen=True)
class ExportOptions:
    filepath: Path
    physics: PhysicsOptions
    meters_per_blender_unit: float = 1.0
    # Output contract: Z-up, metersPerUnit=1; convert transforms/vertices to meters.


@dataclass(frozen=True)
class RetopoResult:
    low_poly: Object  # A new Mesh object with an active, unwrapped and packed UV map.


@dataclass(frozen=True)
class BakeResult:
    textures: Mapping[BakeChannel, Path]  # Saved files for every requested channel.


@dataclass(frozen=True)
class ExportResult:
    filepath: Path  # Final USD with physics and collision schemas authored.
