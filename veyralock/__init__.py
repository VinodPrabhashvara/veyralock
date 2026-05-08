"""VeyraLock package."""

from .crypto import (
    InvalidPasswordOrCorruptFile,
    VeyraLockError,
    decrypt_bytes,
    decrypt_file,
    encrypt_bytes,
    encrypt_file,
)

__all__ = [
    "VeyraLockError",
    "InvalidPasswordOrCorruptFile",
    "encrypt_bytes",
    "decrypt_bytes",
    "encrypt_file",
    "decrypt_file",
]

__version__ = "1.0.0"
