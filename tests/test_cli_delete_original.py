from pathlib import Path
from unittest.mock import patch

from veyralock import cli


def test_encrypt_delete_original_file_yes_removes_source(tmp_path: Path) -> None:
    source = tmp_path / "note.txt"
    source.write_text("secret", encoding="utf-8")

    with patch("getpass.getpass", side_effect=["StrongPassphrase123!", "StrongPassphrase123!"]):
        exit_code = cli.main(["encrypt", str(source), "--delete-original", "--yes"])

    assert exit_code == 0
    assert not source.exists()
    assert (tmp_path / "note.txt.vlock").is_file()


def test_encrypt_delete_original_folder_yes_removes_source(tmp_path: Path) -> None:
    source = tmp_path / "project"
    source.mkdir()
    (source / "file.txt").write_text("secret", encoding="utf-8")

    with patch("getpass.getpass", side_effect=["StrongPassphrase123!", "StrongPassphrase123!"]):
        exit_code = cli.main(["encrypt", str(source), "--delete-original", "--yes"])

    assert exit_code == 0
    assert not source.exists()
    assert (tmp_path / "project.vlock").is_file()


def test_delete_original_is_skipped_when_verification_fails(tmp_path: Path) -> None:
    source = tmp_path / "keep.txt"
    source.write_text("secret", encoding="utf-8")

    with patch("getpass.getpass", side_effect=["StrongPassphrase123!", "StrongPassphrase123!"]):
        with patch("veyralock.cli.verify_encrypted_file", side_effect=cli.VeyraLockError("verify failed")):
            exit_code = cli.main(["encrypt", str(source), "--delete-original", "--yes"])

    assert exit_code == 1
    assert source.exists()
    assert (tmp_path / "keep.txt.vlock").is_file()
