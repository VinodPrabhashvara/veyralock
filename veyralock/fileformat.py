"""Binary format helpers for VeyraLock `.vlock` containers.

The container layout is:

    magic               7 bytes   b"VLOCK1"
    version             1 byte    format version
    kdf_name_len        1 byte
    kdf_name            N bytes   UTF-8, currently ``argon2id``
    salt_len            1 byte
    salt                N bytes
    nonce_len           1 byte
    nonce               N bytes
    filename_len        2 bytes   unsigned big-endian
    filename            N bytes   UTF-8 basename only
    ciphertext_and_tag  remaining bytes

The serialized header is used as AES-GCM additional authenticated data (AAD),
so the metadata is integrity protected even though it is stored in plaintext.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass

MAGIC = b"VLOCK1"
VERSION = 1
KDF_NAME = "argon2id"
NONCE_SIZE = 12
FILENAME_LENGTH_STRUCT = struct.Struct("!H")


class FileFormatError(ValueError):
    """Raised when a .vlock file is invalid or unsupported."""


@dataclass(frozen=True)
class VLockHeader:
    """Parsed metadata from a .vlock file."""

    kdf_name: str
    salt: bytes
    nonce: bytes
    original_name: str
    version: int = VERSION


def _safe_original_name(name: str) -> str:
    cleaned = os.path.basename(name or "").strip()
    return cleaned or "decrypted.bin"


def _pack_u8_length(length: int, field_name: str) -> bytes:
    if not 0 <= length <= 0xFF:
        raise FileFormatError(f"{field_name} is too long for the VeyraLock format.")
    return bytes((length,))


def _read_u8_length(blob: bytes, cursor: int, field_name: str) -> tuple[int, int]:
    if cursor >= len(blob):
        raise FileFormatError(f"Missing {field_name} length in VeyraLock header.")
    return blob[cursor], cursor + 1


def _read_exact(blob: bytes, cursor: int, length: int, field_name: str) -> tuple[bytes, int]:
    end = cursor + length
    if end > len(blob):
        raise FileFormatError(f"Truncated {field_name} field in VeyraLock header.")
    return blob[cursor:end], end


def pack_header(header: VLockHeader) -> bytes:
    """Serialize a validated ``VLockHeader`` into the VeyraLock header format."""
    if header.version != VERSION:
        raise FileFormatError(f"Unsupported VeyraLock format version: {header.version}.")

    normalized_kdf = header.kdf_name.strip().lower()
    if normalized_kdf != KDF_NAME:
        raise FileFormatError(f"Unsupported KDF for VeyraLock format: {header.kdf_name}.")
    if len(header.nonce) != NONCE_SIZE:
        raise FileFormatError("AES-GCM nonce must be 12 bytes.")
    if not header.salt:
        raise FileFormatError("Salt must not be empty.")

    kdf_name = normalized_kdf.encode("utf-8")
    original_name = _safe_original_name(header.original_name).encode("utf-8")
    return b"".join(
        [
            MAGIC,
            bytes((header.version,)),
            _pack_u8_length(len(kdf_name), "KDF name"),
            kdf_name,
            _pack_u8_length(len(header.salt), "salt"),
            header.salt,
            _pack_u8_length(len(header.nonce), "nonce"),
            header.nonce,
            FILENAME_LENGTH_STRUCT.pack(len(original_name)),
            original_name,
        ]
    )


def unpack_header(blob: bytes) -> tuple[VLockHeader, int]:
    """Parse a `.vlock` header and return the header plus ciphertext offset."""
    minimum_size = len(MAGIC) + 1 + 1 + 1 + 1 + FILENAME_LENGTH_STRUCT.size
    if len(blob) < minimum_size:
        raise FileFormatError("File is too small to be a valid .vlock container.")

    cursor = 0
    magic, cursor = _read_exact(blob, cursor, len(MAGIC), "magic")
    if magic != MAGIC:
        raise FileFormatError("File signature does not match VeyraLock format.")

    version, cursor = _read_u8_length(blob, cursor, "version")
    if version != VERSION:
        raise FileFormatError(f"Unsupported VeyraLock format version: {version}.")

    kdf_name_len, cursor = _read_u8_length(blob, cursor, "KDF name")
    if kdf_name_len == 0:
        raise FileFormatError("KDF name must not be empty.")
    kdf_name_bytes, cursor = _read_exact(blob, cursor, kdf_name_len, "KDF name")

    try:
        kdf_name = kdf_name_bytes.decode("utf-8").strip().lower()
    except UnicodeDecodeError as exc:
        raise FileFormatError("KDF name is not valid UTF-8.") from exc
    if kdf_name != KDF_NAME:
        raise FileFormatError(f"Unsupported KDF in VeyraLock header: {kdf_name}.")

    salt_len, cursor = _read_u8_length(blob, cursor, "salt")
    if salt_len == 0:
        raise FileFormatError("Salt length must not be zero.")
    salt, cursor = _read_exact(blob, cursor, salt_len, "salt")

    nonce_len, cursor = _read_u8_length(blob, cursor, "nonce")
    if nonce_len != NONCE_SIZE:
        raise FileFormatError("Invalid AES-GCM nonce length in file header.")
    nonce, cursor = _read_exact(blob, cursor, nonce_len, "nonce")

    if cursor + FILENAME_LENGTH_STRUCT.size > len(blob):
        raise FileFormatError("Missing filename length in VeyraLock header.")
    (original_name_len,) = FILENAME_LENGTH_STRUCT.unpack_from(blob, cursor)
    cursor += FILENAME_LENGTH_STRUCT.size

    original_name_bytes, cursor = _read_exact(
        blob,
        cursor,
        original_name_len,
        "original filename",
    )

    try:
        original_name = original_name_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FileFormatError("Original filename metadata is not valid UTF-8.") from exc

    header = VLockHeader(
        kdf_name=kdf_name,
        salt=salt,
        nonce=nonce,
        original_name=_safe_original_name(original_name),
        version=version,
    )
    return header, cursor
