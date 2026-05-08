import os
from pathlib import Path
from unittest.mock import patch

import pytest
from veyralock.cli import main
from veyralock.crypto import decrypt_bytes, decrypt_file, encrypt_bytes, encrypt_file
from veyralock.fileformat import unpack_header


def test_encrypt_then_decrypt_text_file(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    original_text = "VeyraLock keeps text files safe.\nSecond line.\n"
    source.write_text(original_text, encoding="utf-8")

    encrypted = encrypt_file(source, "correct horse battery staple")
    output = tmp_path / "restored.txt"
    decrypted = decrypt_file(encrypted, "correct horse battery staple", output_path=output)

    assert decrypted == output
    assert decrypted.read_text(encoding="utf-8") == original_text


def test_encrypt_then_decrypt_binary_file(tmp_path: Path) -> None:
    source = tmp_path / "sample.bin"
    original_bytes = b"\x00\xffVeyraLock\x10\x20binary-data"
    source.write_bytes(original_bytes)

    output = tmp_path / "restored.bin"
    encrypted = encrypt_file(source, "correct horse battery staple")
    decrypted = decrypt_file(encrypted, "correct horse battery staple", output_path=output)

    assert decrypted == output
    assert decrypted.read_bytes() == original_bytes


def test_encrypt_then_decrypt_empty_file(tmp_path: Path) -> None:
    source = tmp_path / "empty.dat"
    source.write_bytes(b"")

    encrypted = encrypt_file(source, "correct horse battery staple")
    output = tmp_path / "empty-restored.dat"
    decrypted = decrypt_file(encrypted, "correct horse battery staple", output_path=output)

    assert decrypted == output
    assert decrypted.read_bytes() == b""


def test_encrypt_then_decrypt_large_random_file(tmp_path: Path) -> None:
    source = tmp_path / "large.bin"
    original_bytes = os.urandom(2 * 1024 * 1024)
    source.write_bytes(original_bytes)

    encrypted = encrypt_file(source, "correct horse battery staple")
    output = tmp_path / "large-restored.bin"
    decrypted = decrypt_file(encrypted, "correct horse battery staple", output_path=output)

    assert decrypted == output
    assert decrypted.read_bytes() == original_bytes


def test_encrypt_without_compression_still_round_trips() -> None:
    original_bytes = (b"A" * 128) + (b"\x00\xff" * 32)
    package = encrypt_bytes(
        original_bytes,
        "correct horse battery staple",
        original_name="sample.bin",
        compress=False,
    )

    decrypted, header = decrypt_bytes(package, "correct horse battery staple")

    assert decrypted == original_bytes
    assert header.original_name == "file"


def test_encrypt_then_decrypt_folder_round_trip(tmp_path: Path) -> None:
    source_dir = tmp_path / "project"
    nested_dir = source_dir / "docs"
    empty_dir = source_dir / "empty"
    nested_dir.mkdir(parents=True)
    empty_dir.mkdir()
    (source_dir / "root.txt").write_text("root-data", encoding="utf-8")
    (nested_dir / "readme.md").write_text("# nested", encoding="utf-8")
    (nested_dir / "blob.bin").write_bytes(b"\x00\x01\x02\x03")

    encrypted = encrypt_file(source_dir, "correct horse battery staple")
    restored_dir = tmp_path / "restored-project"
    decrypted = decrypt_file(
        encrypted,
        "correct horse battery staple",
        output_path=restored_dir,
    )

    assert decrypted == restored_dir
    assert (decrypted / "root.txt").read_text(encoding="utf-8") == "root-data"
    assert (decrypted / "docs" / "readme.md").read_text(encoding="utf-8") == "# nested"
    assert (decrypted / "docs" / "blob.bin").read_bytes() == b"\x00\x01\x02\x03"
    assert (decrypted / "empty").is_dir()


def test_output_file_extension_is_vlock(tmp_path: Path) -> None:
    source = tmp_path / "report.txt"
    source.write_text("secret", encoding="utf-8")

    encrypted = encrypt_file(source, "correct horse battery staple")

    assert encrypted.name == "report.txt.vlock"
    assert encrypted.suffix == ".vlock"


def test_original_filename_is_not_exposed_in_header() -> None:
    package = encrypt_bytes(
        b"secret payload",
        "correct horse battery staple",
        original_name="payroll-2026.xlsx",
    )

    header, _ = unpack_header(package)

    assert header.original_name == "file"
    assert header.original_name != "payroll-2026.xlsx"


def test_original_file_is_not_deleted_unless_requested(tmp_path: Path) -> None:
    source = tmp_path / "keep.txt"
    source.write_text("do not delete", encoding="utf-8")

    with patch("getpass.getpass", side_effect=["StrongPassphrase123!", "StrongPassphrase123!"]):
        exit_code = main(["encrypt", str(source), "--yes"])

    assert exit_code == 0
    assert source.exists()
    assert source.read_text(encoding="utf-8") == "do not delete"
    assert (tmp_path / "keep.txt.vlock").is_file()


@pytest.mark.skipif(os.name == "nt", reason="':' is not a valid Windows filename")
def test_folder_round_trip_supports_posix_colon_filenames(tmp_path: Path) -> None:
    source_dir = tmp_path / "project"
    source_dir.mkdir()
    (source_dir / "notes:2026.txt").write_text("ok", encoding="utf-8")

    encrypted = encrypt_file(source_dir, "correct horse battery staple")
    restored_dir = tmp_path / "restored-project"
    decrypted = decrypt_file(
        encrypted,
        "correct horse battery staple",
        output_path=restored_dir,
    )

    assert (decrypted / "notes:2026.txt").read_text(encoding="utf-8") == "ok"
