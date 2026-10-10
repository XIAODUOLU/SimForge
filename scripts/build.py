"""Run python3 scripts/build.py to build legacy and Blender 4.2+ Extension packages."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "simforge"


def build():
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    for kind in ("legacy", "extension"):
        archive = destination / f"simforge-1.0.0-{kind}.zip"
        with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
            # Include the license in both installable distributions.
            license_path = "simforge/LICENSE" if kind == "legacy" else "LICENSE"
            bundle.write(ROOT / "LICENSE", license_path)
            for path in sorted(SOURCE.rglob("*")):
                if not path.is_file() or '__pycache__' in path.parts:
                    continue
                if path.suffix not in {'.py', '.toml'}:
                    continue
                if kind == 'legacy' and path.name == 'blender_manifest.toml':
                    continue
                relative = path.relative_to(SOURCE)
                bundle.write(path, str(Path('simforge') / relative) if kind == 'legacy' else str(relative))
        print(archive)


if __name__ == '__main__':
    build()
