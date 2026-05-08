from pathlib import Path

from veyralock.cli import main
from veyralock.crypto import encrypt_file


def test_info_command_shows_safe_metadata(tmp_path: Path, capsys) -> None:
    source = tmp_path / "sample.bin"
    source.write_bytes(b"hello world")
    encrypted = encrypt_file(source, "CorrectHorseBatteryStaple123!")

    exit_code = main(["info", str(encrypted)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Format version: 1" in captured.out
    assert "KDF: argon2id" in captured.out
    assert "Salt size: 16 bytes" in captured.out
    assert "Nonce size: 12 bytes" in captured.out
