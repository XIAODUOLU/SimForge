# SimForge

<p align="center">
  <a href="assets/SimForge.svg"><img src="assets/SimForge_Horizontal.svg" alt="SimForge — green solid geometry meets orange wireframe geometry" width="400"></a>
</p>

<p align="center">
  <strong>From AI-generated meshes to physics-enabled USD assets.</strong>
</p>

<p align="center">
  <a href="#installation"><img src="https://img.shields.io/badge/version-1.0.0-2563EB" alt="Version 1.0.0"></a>
  <a href="#compatibility"><img src="https://img.shields.io/badge/Blender-4.x%20%7C%205.x-F5792A?logo=blender&amp;logoColor=white" alt="Blender 4.x and 5.x"></a>
  <a href="#validation"><img src="https://img.shields.io/badge/Isaac%20Sim-6.x%20validated-76B900" alt="Validated in Isaac Sim 6.x"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-22A06B" alt="MIT License"></a>
</p>

<p align="center">
  <a href="#showcase">Showcase</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#documentation">Documentation</a>
</p>

<p align="center">
  <a href="assets/readme-hero.png"><img src="assets/readme-hero.png" alt="hero"></a>
  <br>
</p>

SimForge brings mesh preparation and simulation asset authoring into one Blender panel. It turns high-poly meshes from Hy3D, Tripo, and other generators into reusable USD assets for NVIDIA Isaac Sim, combining retopology, UV generation, five-channel PBR baking, and physics-aware export.

Prepare the geometry, carry its appearance onto the low-poly mesh, and configure collision, mass, friction, and restitution before export. The result is an asset with both visual materials and physical properties, ready to place in an Isaac Sim scene.

```text
High-poly mesh → Retopology and UVs → PBR textures → USD asset with collision and physics
```

## Showcase

### Retopology and visual consistency

The mug example follows the same asset through geometry preparation, texture baking, and simulation. In both Blender views below, the source mesh is on the left and the prepared low-poly mesh is on the right.

<table>
  <tr>
    <th width="50%">Retopologized geometry</th>
    <th width="50%">Baked appearance</th>
  </tr>
  <tr>
    <td>
      <a href="assets/retopo_wireframe.png"><img src="assets/retopo_wireframe.png" alt="wireframe" width="100%"></a>
    </td>
    <td>
      <a href="assets/retopo_render.png"><img src="assets/retopo_render.png" alt="render" width="100%"></a>
    </td>
  </tr>
  <tr>
    <td>The wireframe exposes the resulting topology.</td>
    <td>The rendered view shows visual consistency.</td>
  </tr>
</table>

### Collision and rigid-body properties in Isaac Sim

The Isaac Sim screenshot shows the exported mug with its collision geometry overlaid and its rigid-body properties. The animation demonstrates the resulting interaction: a ball drops into the mug and settles inside its hollow interior.

<table>
  <tr>
    <th width="50%">Collision inspection</th>
    <th width="50%">Hollow-object interaction</th>
  </tr>
  <tr>
    <td>
      <a href="assets/sim.png"><img src="assets/sim.png" alt="sim_physics" width="100%"></a>
    </td>
    <td>
      <a href="assets/sim.gif"><img src="assets/sim.gif" alt="sim_interactive" width="100%"></a>
    </td>
  </tr>
  <tr>
    <td>Inspect the collision approximation and rigid-body settings.</td>
    <td>Watch the cavity receive a falling ball during simulation.</td>
  </tr>
</table>

For hollow assets such as cups and containers, choose **Convex Decomposition** when exporting and inspect the resulting collider in Isaac Sim. A single **Convex Hull** spans the opening and prevents objects from entering the cavity. The example demonstrates the mug's behavior; collision fidelity depends on the input geometry and the resulting decomposition.

## Features

| Step | What SimForge produces |
| --- | --- |
| **Retopo** | An independent low-poly mesh with Smart UV Project and packed UV islands; the source mesh remains available for baking. |
| **Bake** | Normal, base color, metallic, roughness, and alpha textures, connected to a material on the low-poly mesh. |
| **Export** | A USD asset with portable texture references, visual and physics materials, and collision settings for dynamic or static use. |

Export supports convex hull and convex decomposition collision approximations, configurable rigid-body mass, friction, and restitution. You can also export an existing prepared mesh without running Retopo or Bake first.

## Compatibility

- **Blender 4.x and 5.x** are the supported version families. Blender 4.0–4.1 use the Legacy add-on package; Blender 4.2–5.x use the Extension package.
- **Isaac Sim 6.x** has been used to validate exported asset physics. Isaac Sim is required to consume and simulate the USD assets, not to run the Blender add-on.
- **Python 3.10+** is required only when building installation packages from source. The add-on runs with Blender's bundled Python.
- **Cycles GPU rendering** must be configured in Blender preferences for texture baking.

See the [compatibility guide](docs/compatibility.md) for test scope and version-specific behavior.

## Installation

From the repository root, build both installation packages:

```bash
python3 scripts/build.py
```

| Blender version | Package | Install from Blender |
| --- | --- | --- |
| 4.0–4.1 | `dist/simforge-1.0.0-legacy.zip` | **Edit → Preferences → Add-ons → Install**, then enable SimForge. |
| 4.2–5.x | `dist/simforge-1.0.0-extension.zip` | **Edit → Preferences → Get Extensions → Install from Disk**. |

On first enable, SimForge uses available USD Python bindings or installs `usd-core>=24.5,<27` into Blender's user scripts directory. A first-time installation may require network access. Installation packages do not bundle dependency wheels.

## Quick start

1. Import a high-poly mesh, save the `.blend` file, and switch to **Object Mode**.
2. In the 3D View, press **N** and open the **SimForge** tab.
3. Select the source mesh and assign it to **High Poly**, or leave that field empty and make the mesh active.
4. Set the retopology options and click **Retopo**. SimForge creates a separate low-poly mesh with UVs.
5. Set the texture output directory and click **Bake** to transfer all five PBR channels from the source mesh.
6. Choose the USD path, body type, collision approximation, and physics settings, then click **Export**.
7. Import or reference the USD in an Isaac Sim scene with a physics scene, inspect the collider, and run the simulation.

For an existing prepared mesh, assign it to **Low Poly** and export directly. It must have an active UV map and valid materials. Paths beginning with `//` are relative to the saved `.blend` file; choose an absolute path if the scene has not been saved.

## USD output

The export creates a reusable `/Asset` component in Z-up, meter-based coordinates. Textures are stored beside the USD in `<asset_name>_textures/` and referenced by relative paths; keep the USD and its texture directory together when moving the asset.

Dynamic assets include a rigid body and mass. Static assets include collision without a dynamic rigid body. The visual material and physics material remain separate. The consuming Isaac Sim scene supplies its own global physics scene. SimForge does not overwrite existing USD files or texture directories.

## Validation

Package installation and the complete Retopo → GPU Bake → USD Export workflow have been tested in Blender 4.x and 5.x. Assets exported from both version families have undergone physics testing in Isaac Sim 6.x. The repository includes Blender integration tests and an Isaac Sim asset test; the [compatibility guide](docs/compatibility.md#validation-procedure) has the reproduction commands and scope.

## Documentation

- [Compatibility guide](docs/compatibility.md) — installation formats, version differences, and validation.
- [Development guide](docs/development.md) — service entry points, build commands, and contribution conventions.
- [Architecture](docs/architecture.md) — module boundaries and processing contracts.

## License

SimForge is available under the [MIT License](LICENSE).
