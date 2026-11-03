"""Build a clean source-and-evidence ZIP, excluding local state and backups."""
from __future__ import annotations

from pathlib import Path
import zipfile

from inventory_app import config

ROOT = config.PROJECT_ROOT
OUTPUT = ROOT / "submission_bundle" / "sitestock_submission.zip"
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "_private_archive", "artifacts", "logs", "submission_bundle",
    "node_modules", "dist", "build",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".joblib", ".log", ".tmp"}
EXCLUDED_NAMES = {"inventory.db", "inventory.db-wal", "inventory.db-shm", ".coverage", ".sudo_as_admin_successful"}


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.name.startswith(".env") and path.name != ".env.example":
        return False
    return path.is_file()


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in ROOT.rglob("*") if included(path))
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for path in files:
            archive.write(path, Path("SiteStock") / path.relative_to(ROOT))
    with zipfile.ZipFile(OUTPUT, "r") as archive:
        names = archive.namelist()
        unsafe = [name for name in names if any(part in EXCLUDED_DIRS for part in Path(name).parts)]
        if unsafe:
            OUTPUT.unlink(missing_ok=True)
            raise RuntimeError(f"Submission archive contains excluded paths: {unsafe[:5]}")
    print(f"Submission archive created: {OUTPUT.relative_to(ROOT)} ({len(files)} files, {OUTPUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
