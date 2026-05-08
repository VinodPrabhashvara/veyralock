import io
from pathlib import Path
from veyralock.crypto import (
    InvalidPasswordOrCorruptFile,
    VeyraLockError,
    _encrypt_payload,
    decrypt_bytes,
    decrypt_file,
    encrypt_bytes,
)
from veyralock.fileformat import MAGIC
from zipfile import ZipFile

import pytest


def test_tampered_ciphertext_is_detected() -> None:
    package = bytearray(
        encrypt_bytes(b"important document bytes", "strong-password", original_name="doc.pdf")
    )
    package[-1] ^= 0x01

    with pytest.raises(InvalidPasswordOrCorruptFile):
        decrypt_bytes(bytes(package), "strong-password")


def test_tampered_header_is_detected() -> None:
    package = bytearray(
        encrypt_bytes(b"important document bytes", "strong-password", original_name="doc.pdf")
    )
    package[len(MAGIC) + 1 + 1 + len("argon2id") + 1] ^= 0x01

    with pytest.raises(InvalidPasswordOrCorruptFile):
        decrypt_bytes(bytes(package), "strong-password")


def test_invalid_magic_is_rejected() -> None:
    package = bytearray(
        encrypt_bytes(b"important document bytes", "strong-password", original_name="doc.pdf")
    )
    package[0] ^= 0x01

    with pytest.raises(VeyraLockError):
        decrypt_bytes(bytes(package), "strong-password")


def test_folder_archive_path_traversal_is_rejected(tmp_path: Path) -> None:
    archive = io.BytesIO()
    with ZipFile(archive, "w") as zip_handle:
        zip_handle.writestr("../escape.txt", b"malicious")

    package = _encrypt_payload(
        archive.getvalue(),
        "strong-password",
        original_name="project",
        compress=False,
        is_directory=True,
        time_cost=3,
        memory_cost=65536,
        parallelism=4,
    )
    encrypted_file = tmp_path / "archive.vlock"
    encrypted_file.write_bytes(package)

    with pytest.raises(VeyraLockError):
        decrypt_file(encrypted_file, "strong-password", output_path=tmp_path / "restored")
