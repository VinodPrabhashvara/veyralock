"""Path and file handling helpers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

VLOCK_EXTENSION = ".vlock"
DELETE_OVERWRITE_CHUNK_SIZE = 1024 * 1024


def ensure_input_path(path: str | Path) -> Path:
    """Validate that the input path exists."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Input path not found: {resolved}")
    return resolved


def ensure_input_file(path: str | Path) -> Path:
    """Validate that the input path points to a readable file."""
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"Input file not found: {resolved}")
    return resolved


def ensure_output_path(path: str | Path, *, overwrite: bool = False) -> Path:
    """Validate that an output path is safe to write."""
    resolved = Path(path)
    if resolved.exists() and not overwrite:
        raise FileExistsError(
            f"Output file already exists: {resolved}. Use overwrite to replace it."
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def ensure_output_directory(path: str | Path, *, overwrite: bool = False) -> Path:
    """Validate that a directory path is safe to create or replace."""
    resolved = Path(path)
    if resolved.exists():
        if not overwrite:
            raise FileExistsError(
                f"Output path already exists: {resolved}. Use overwrite to replace it."
            )
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            resolved.unlink()

    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def best_effort_delete_file(path: str | Path) -> None:
    """Best-effort overwrite a file once, then delete it.

    This reduces obvious recovery in some cases, but it is not guaranteed on
    SSDs, cloud-synced folders, copy-on-write storage, or journaling filesystems.
    """
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"Input file not found: {resolved}")

    file_size = resolved.stat().st_size
    with resolved.open("r+b", buffering=0) as handle:
        remaining = file_size
        while remaining > 0:
            chunk_size = min(DELETE_OVERWRITE_CHUNK_SIZE, remaining)
            handle.write(os.urandom(chunk_size))
            remaining -= chunk_size
        handle.flush()
        os.fsync(handle.fileno())

    resolved.unlink()


def encrypted_output_path(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Resolve the output path for encryption."""
    source = Path(input_path)
    if output_path is not None:
        return Path(output_path)
    return source.with_name(source.name + VLOCK_EXTENSION)


def decrypted_output_path(
    input_path: str | Path,
    original_name: str,
    output_path: str | Path | None = None,
) -> Path:
    """Resolve the output path for decryption."""
    source = Path(input_path)
    if output_path is not None:
        return Path(output_path)

    if source.name.endswith(VLOCK_EXTENSION):
        return source.with_name(original_name)

    return source.with_name(f"{source.stem}.decrypted")
