# SimForge

**From AI-3D-generated meshes to simulation-ready assets.**

SimForge is an open-source Blender add-on for preparing meshes from Hy3D, Tripo, and other AI 3D generation tools for simulation. It brings retopology, PBR texture baking, and USD export for NVIDIA Isaac Sim into a single workflow inside Blender.

```text
High-poly asset → Retopology & UVs → PBR baking → USD with physics & collision
```

## Project status

**Early development · version 0.1.0**

The add-on provides retopology, base-color/normal baking, and USD export with collision and rigid-body schemas. Export has been tested in Blender 4.x; validation inside Isaac Sim is still pending.

## Planned capabilities

| Stage | Intended output |
| --- | --- |
| **Retopo** | A separate low-poly mesh with Smart UV Project and packed UV islands |
| **Bake** | Normal, base color, metallic, roughness, and alpha textures transferred from the original high-poly source |
| **Export** | A reusable USD asset with materials, collision geometry, and rigid-body properties for Isaac Sim |

The workflow preserves the original high-poly mesh as the baking source. Export is designed to support dynamic and static assets, configurable mass and friction, and convex hull or convex decomposition collision approximations.

## Requirements

- **Blender 4.x–5.x** is the compatibility target. Registration, USD export, pip dependency installation and Extension manifest validation pass in **Blender 4.x**. Blender 5.x runtime validation is pending; this does not establish coverage of every release in either range.
- **Python 3.10 or later** is needed to build installation packages from source using the provided script. The add-on itself runs inside Blender's Python environment.
- On first enable, SimForge uses existing USD Python bindings if available, otherwise installs `usd-core>=24.5,<27` through Blender's Python pip. The first installation requires network access. Dependencies are cached in Blender's user scripts directory under `simforge_dependencies`, independently of system Python. Installation packages contain no dependency wheels.

See the [compatibility guide](docs/compatibility.md) for the validation scope and adapter boundaries.

## Installation

Build the packages from the repository root:

```bash
python3 scripts/build.py
```

| Blender version | Package | Installation |
| --- | --- | --- |
| 4.0–4.1 | `dist/simforge-0.1.0-legacy.zip` | Preferences → Add-ons → Install, then enable SimForge |
| 4.2–5.x | `dist/simforge-0.1.0-extension.zip` | Preferences → Get Extensions → menu → Install from Disk |

## Getting started

1. Import a high-poly asset into Blender and switch to Object Mode.
2. Press `N` in the 3D View and open the **SimForge** tab.
3. Assign **High Poly**, or leave it empty to use the active object for Retopo.
4. Configure the target face count, UV settings, texture output, and USD physics settings.

The processing order is **Retopo → Bake → Export**. Export also accepts an existing prepared mesh with an active UV map and valid materials. Default paths use Blender's `//` notation: save the `.blend` file first or choose absolute output paths.

Export writes a reusable `/Asset` component with Z-up, meter coordinates, relative textures in `<asset_name>_textures/`, and a separate physics material binding that preserves the visual material. Move the USD and its texture directory together. Existing USD files and texture directories are never overwritten.

Dynamic assets receive a rigid body and mass in kilograms; static assets receive collision only. The default parameters are 1 kg, convex hull collision, static/dynamic friction 0.5, and restitution 0. Adjust these to the object's measured properties; use convex decomposition for concave geometry. Isaac Sim computes collider decomposition, center of mass and inertia when loading. The asset does not create a global physics scene.

## Documentation

- [Development guide](docs/development.md): implement the three services, use adapters, build packages, and run checks.
- [Architecture](docs/architecture.md): module responsibilities, data contracts, processing requirements, and resource cleanup.
- [Compatibility](docs/compatibility.md): supported ranges, validation scope, dependency handling, and validation procedures.

## Roadmap

- [x] Add-on registration, settings, and sidebar
- [x] Service contracts, validation, and basic version adapters
- [x] Legacy and Extension packaging
- [x] Retopology with mesh validation and UV generation
- [x] PBR baking
- [x] USD export with physics and collision authoring
- [ ] Runtime coverage across Blender 4.x and 5.x
- [ ] Asset validation in Isaac Sim

## License

SimForge is released under the [MIT License](LICENSE).
