# SimForge

**From AI-3D-generated meshes to simulation-ready assets.**

SimForge is an open-source Blender add-on for preparing meshes from Hy3D, Tripo, and other AI 3D generation tools for simulation. It brings retopology, PBR texture baking, and USD export for NVIDIA Isaac Sim into a single workflow inside Blender.

```text
High-poly asset → Retopology & UVs → PBR baking → USD with physics & collision
```

## Project status

**Early development · version 0.1.0**

The add-on foundation is available: a Blender sidebar, persistent settings, input validation, version adapters, and installation packages. The three processing stages are currently implementation stubs. With valid inputs, their buttons report that implementation is required; this version does not yet generate simulation-ready assets.

## Planned capabilities

| Stage | Intended output |
| --- | --- |
| **Retopo** | A separate low-poly mesh with Smart UV Project and packed UV islands |
| **Bake** | Normal, base color, metallic, roughness, and alpha textures transferred from the original high-poly source |
| **Export** | A reusable USD asset with materials, collision geometry, and rigid-body properties for Isaac Sim |

The workflow preserves the original high-poly mesh as the baking source. Export is designed to support dynamic and static assets, configurable mass and friction, and convex hull or convex decomposition collision approximations.

## Requirements

- **Blender 4.x–5.x** is the compatibility target. Registration and interface smoke tests and Extension manifest validation pass in the available **Blender 4.x** environment. Blender 5.x runtime validation and processing-service validation are pending; this does not establish coverage of every release in either range.
- **Python 3.10 or later** is needed to build installation packages from source using the provided script. The add-on itself runs inside Blender's Python environment.
- USD/PhysX Python bindings are optional at registration time. The export implementation will require suitable bindings for physics authoring or a separately implemented Isaac Sim post-processing step.

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

The intended processing order is **Retopo → Bake → Export**. Processing is not available in the current scaffold. Default paths use Blender's `//` notation: save the `.blend` file first or choose absolute output paths.

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
- [ ] USD export with physics and collision authoring
- [ ] Runtime coverage across Blender 4.x and 5.x
- [ ] Asset validation in Isaac Sim

## License

SimForge is released under the [MIT License](LICENSE).
