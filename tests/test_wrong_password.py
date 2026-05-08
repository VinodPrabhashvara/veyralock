import pytest

from veyralock.crypto import InvalidPasswordOrCorruptFile, decrypt_bytes, encrypt_bytes


def test_decrypt_with_wrong_password_fails() -> None:
    package = encrypt_bytes(b"secret payload", "right-password", original_name="secret.txt")

    with pytest.raises(InvalidPasswordOrCorruptFile):
        decrypt_bytes(package, "wrong-password")
