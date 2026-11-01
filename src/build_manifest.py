
import hashlib
import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INCLUDED_DIRS = [
    ROOT / "src",
    ROOT / "sql",
    ROOT / "docs",
    ROOT / "data" / "generated",
    ROOT / "reports",
]

EXCLUDED_FILES = {
    "source_manifest.json",
    "validation_summary.json",
}

SEED = 20261022


def sha256_file(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def build_manifest():
    files = []

    for directory in INCLUDED_DIRS:
        if not directory.exists():
            continue

        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue

            if path.name in EXCLUDED_FILES:
                continue

            relative_path = path.relative_to(ROOT).as_posix()

            files.append({
                "path": relative_path,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })

    manifest = {
        "project": "Employee Learning Pathway",
        "random_seed": SEED,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "file_count": len(files),
        "files": files,
    }

    output = ROOT / "docs" / "source_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8"
    )

    print("SOURCE MANIFEST GENERATED")
    print("=" * 45)
    print("Files hashed:", len(files))
    print("Output:", output)


if __name__ == "__main__":
    build_manifest()
