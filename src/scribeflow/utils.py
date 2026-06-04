"""General utility helpers for ScribeFlow."""

from pathlib import Path


def ensure_directories(root: Path, directories: list[Path]) -> None:
    """Create required directories if they do not exist."""
    for relative_dir in directories:
        (root / relative_dir).mkdir(parents=True, exist_ok=True)


def normalize_filename(filename: str) -> str:
    """Normalize a filename for stable ledger storage."""
    name = Path(filename).name.strip().lower().replace(" ", "_")
    return name


def to_relative_posix(path: Path, root: Path) -> str:
    """Return a workspace-relative POSIX path string."""
    return path.resolve().relative_to(root.resolve()).as_posix()
