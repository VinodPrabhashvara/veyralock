"""Core encryption and decryption operations."""

from __future__ import annotations

import io
import os
import stat
import struct
import shutil
import zlib
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .fileformat import (
    FileFormatError,
    KDF_NAME,
    NONCE_SIZE,
    VLockHeader,
    pack_header,
    unpack_header,
)
from .password import (
    DEFAULT_MEMORY_COST,
    DEFAULT_PARALLELISM,
    DEFAULT_TIME_COST,
    derive_key,
    generate_salt,
)
from .utils import (
    decrypted_output_path,
    encrypted_output_path,
    ensure_input_path,
    ensure_input_file,
    ensure_output_directory,
    ensure_output_path,
)


class VeyraLockError(Exception):
    """Base exception for the VeyraLock package."""


class InvalidPasswordOrCorruptFile(VeyraLockError):
    """Raised when decryption fails due to a wrong password or tampering."""


PAYLOAD_MAGIC = b"VLPAY1"
PAYLOAD_FLAG_COMPRESSED = 0x01
PAYLOAD_FLAG_DIRECTORY_ARCHIVE = 0x02
PAYLOAD_FLAG_EMBEDDED_NAME = 0x04
PAYLOAD_NAME_LENGTH_STRUCT = struct.Struct("!H")
GENERIC_FILE_HEADER_NAME = "file"
GENERIC_DIRECTORY_HEADER_NAME = "folder"
ARCHIVE_COPY_BUFFER_SIZE = 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10000
MAX_ARCHIVE_MEMBER_SIZE = 1024 * 1024 * 1024
MAX_TOTAL_ARCHIVE_SIZE = 5 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class PayloadEnvelope:
    """Normalized decrypted payload details."""

    data: bytes
    is_directory: bool
    original_name: str | None = None


def _validate_kdf_parameters(
    *,
    time_cost: int,
    memory_cost: int,
    parallelism: int,
) -> None:
    """Keep the v1 file format on fixed Argon2id parameters.

    The current header format records the KDF name but not alternate Argon2
    tuning values, so encryption must use the project defaults to ensure files
    remain decryptable across environments.
    """
    if (
        time_cost != DEFAULT_TIME_COST
        or memory_cost != DEFAULT_MEMORY_COST
        or parallelism != DEFAULT_PARALLELISM
    ):
        raise ValueError(
            "VeyraLock format v1 uses fixed Argon2id parameters and does not "
            "support overriding time_cost, memory_cost, or parallelism."
        )


def _build_directory_archive(directory: Path, *, compress: bool) -> bytes:
    """Create a ZIP archive of a directory in memory while preserving structure."""
    compression = ZIP_DEFLATED if compress else ZIP_STORED
    buffer = io.BytesIO()

    with ZipFile(buffer, "w", compression=compression) as archive:
        for current_root, dirnames, filenames in os.walk(directory):
            dirnames.sort()
            filenames.sort()

            root_path = Path(current_root)
            relative_root = root_path.relative_to(directory)

            if relative_root != Path(".") and not dirnames and not filenames:
                directory_name = relative_root.as_posix().rstrip("/") + "/"
                archive.writestr(ZipInfo(directory_name), b"")

            for filename in filenames:
                file_path = root_path / filename
                archive.write(file_path, arcname=file_path.relative_to(directory).as_posix())

    return buffer.getvalue()


def _validate_archive_member_path(member_name: str, destination: Path) -> Path:
    """Resolve a ZIP member path and reject traversal or absolute paths."""
    normalized = member_name.replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        raise VeyraLockError("Archive contains an invalid absolute or empty path.")

    raw_parts = [part for part in normalized.split("/") if part]
    if not raw_parts:
        raise VeyraLockError("Archive contains an invalid empty path.")
    if any(part in {".", ".."} for part in raw_parts):
        raise VeyraLockError("Archive contains a path traversal entry.")
    if os.name == "nt" and any(":" in part for part in raw_parts):
        raise VeyraLockError("Archive contains an invalid path component.")

    candidate = (destination / Path(*raw_parts)).resolve()
    root = destination.resolve()
    if os.path.commonpath((str(root), str(candidate))) != str(root):
        raise VeyraLockError("Archive extraction would escape the selected output directory.")

    return candidate


def _extract_directory_archive(archive_bytes: bytes, destination: Path, *, overwrite: bool) -> Path:
    """Safely extract a ZIP archive into a destination directory."""
    try:
        with ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise VeyraLockError("Archive contains too many members to extract safely.")

            total_size = 0
            for member in members:
                unix_mode = member.external_attr >> 16
                if stat.S_ISLNK(unix_mode):
                    raise VeyraLockError("Archive contains an unsupported symbolic link entry.")
                if member.file_size > MAX_ARCHIVE_MEMBER_SIZE:
                    raise VeyraLockError("Archive member is too large to extract safely.")
                total_size += member.file_size
                if total_size > MAX_TOTAL_ARCHIVE_SIZE:
                    raise VeyraLockError("Archive is too large to extract safely.")
                _validate_archive_member_path(member.filename, destination)

            root = ensure_output_directory(destination, overwrite=overwrite)

            for member in members:
                target = _validate_archive_member_path(member.filename, root)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as source_handle, target.open("wb") as target_handle:
                    shutil.copyfileobj(
                        source_handle,
                        target_handle,
                        length=ARCHIVE_COPY_BUFFER_SIZE,
                    )
    except OSError:
        raise
    except VeyraLockError:
        raise
    except Exception as exc:
        raise VeyraLockError("Decrypted folder archive is invalid or unsafe to extract.") from exc

    return root


def _wrap_payload(
    plaintext: bytes,
    *,
    compress: bool,
    is_directory: bool = False,
    original_name: str | None = None,
) -> bytes:
    """Wrap plaintext with internal metadata before authenticated encryption."""
    flags = 0
    payload = plaintext

    if original_name is not None:
        name_bytes = original_name.encode("utf-8")
        if len(name_bytes) > 0xFFFF:
            raise VeyraLockError("Original filename is too long to store safely.")
        payload = PAYLOAD_NAME_LENGTH_STRUCT.pack(len(name_bytes)) + name_bytes + payload
        flags |= PAYLOAD_FLAG_EMBEDDED_NAME

    if compress:
        compressed = zlib.compress(payload)
        if len(compressed) < len(payload):
            payload = compressed
            flags |= PAYLOAD_FLAG_COMPRESSED

    if is_directory:
        flags |= PAYLOAD_FLAG_DIRECTORY_ARCHIVE

    return PAYLOAD_MAGIC + bytes((flags,)) + payload


def _unwrap_payload(payload: bytes) -> PayloadEnvelope:
    """Recover plaintext from an internal encrypted payload wrapper.

    Files encrypted before this wrapper existed are still accepted by falling
    back to the decrypted bytes unchanged.
    """
    if not payload.startswith(PAYLOAD_MAGIC):
        return PayloadEnvelope(data=payload, is_directory=False)

    if len(payload) < len(PAYLOAD_MAGIC) + 1:
        raise VeyraLockError("Encrypted payload metadata is incomplete.")

    flags = payload[len(PAYLOAD_MAGIC)]
    data = payload[len(PAYLOAD_MAGIC) + 1 :]

    if flags & PAYLOAD_FLAG_COMPRESSED:
        try:
            data = zlib.decompress(data)
        except zlib.error as exc:
            raise InvalidPasswordOrCorruptFile(
                "Decryption failed. The file contents are corrupted."
            ) from exc

    original_name = None
    if flags & PAYLOAD_FLAG_EMBEDDED_NAME:
        if len(data) < PAYLOAD_NAME_LENGTH_STRUCT.size:
            raise VeyraLockError("Encrypted payload metadata is incomplete.")

        (name_length,) = PAYLOAD_NAME_LENGTH_STRUCT.unpack_from(data, 0)
        name_start = PAYLOAD_NAME_LENGTH_STRUCT.size
        name_end = name_start + name_length
        if name_end > len(data):
            raise VeyraLockError("Encrypted payload metadata is truncated.")

        try:
            original_name = data[name_start:name_end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise VeyraLockError("Encrypted payload filename is not valid UTF-8.") from exc

        data = data[name_end:]

    return PayloadEnvelope(
        data=data,
        is_directory=bool(flags & PAYLOAD_FLAG_DIRECTORY_ARCHIVE),
        original_name=original_name,
    )


def _ensure_distinct_paths(source: Path, destination: Path) -> None:
    """Prevent destructive in-place operations."""
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output paths must be different.")


def _encrypt_payload(
    plaintext: bytes,
    password: str | bytes,
    *,
    original_name: str,
    compress: bool,
    is_directory: bool,
    time_cost: int,
    memory_cost: int,
    parallelism: int,
) -> bytes:
    """Encrypt normalized payload bytes into the .vlock container format."""
    if not isinstance(plaintext, bytes):
        raise TypeError("Plaintext must be bytes.")

    _validate_kdf_parameters(
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
    )

    salt = generate_salt()
    nonce = os.urandom(NONCE_SIZE)
    key = derive_key(
        password,
        salt,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
    )
    header = VLockHeader(
        kdf_name=KDF_NAME,
        salt=salt,
        nonce=nonce,
        original_name=GENERIC_DIRECTORY_HEADER_NAME if is_directory else GENERIC_FILE_HEADER_NAME,
    )
    header_bytes = pack_header(header)
    payload = _wrap_payload(
        plaintext,
        compress=compress,
        is_directory=is_directory,
        original_name=original_name,
    )
    ciphertext = AESGCM(key).encrypt(nonce, payload, header_bytes)
    return header_bytes + ciphertext


def _decrypt_payload(package: bytes, password: str | bytes) -> tuple[PayloadEnvelope, VLockHeader]:
    """Decrypt a .vlock package and return the normalized payload plus header."""
    if not isinstance(package, bytes):
        raise TypeError("Encrypted package must be bytes.")

    try:
        header, payload_offset = unpack_header(package)
    except FileFormatError as exc:
        raise VeyraLockError(str(exc)) from exc

    protected_header = package[:payload_offset]
    ciphertext = package[payload_offset:]
    if not ciphertext:
        raise VeyraLockError("Encrypted payload is empty.")

    key = derive_key(
        password,
        header.salt,
        time_cost=DEFAULT_TIME_COST,
        memory_cost=DEFAULT_MEMORY_COST,
        parallelism=DEFAULT_PARALLELISM,
    )

    try:
        payload = AESGCM(key).decrypt(header.nonce, ciphertext, protected_header)
    except InvalidTag as exc:
        raise InvalidPasswordOrCorruptFile(
            "Decryption failed. The password is incorrect or the file was modified."
        ) from exc

    return _unwrap_payload(payload), header


def encrypt_bytes(
    plaintext: bytes,
    password: str | bytes,
    *,
    original_name: str = "data.bin",
    compress: bool = True,
    time_cost: int = DEFAULT_TIME_COST,
    memory_cost: int = DEFAULT_MEMORY_COST,
    parallelism: int = DEFAULT_PARALLELISM,
) -> bytes:
    """Encrypt raw bytes into the .vlock container format."""
    return _encrypt_payload(
        plaintext,
        password,
        original_name=original_name,
        compress=compress,
        is_directory=False,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
    )


def decrypt_bytes(package: bytes, password: str | bytes) -> tuple[bytes, VLockHeader]:
    """Decrypt a .vlock package and return plaintext plus parsed header."""
    envelope, header = _decrypt_payload(package, password)
    return envelope.data, header


def encrypt_file(
    input_path: str | Path,
    password: str | bytes,
    *,
    output_path: str | Path | None = None,
    compress: bool = True,
    overwrite: bool = False,
    time_cost: int = DEFAULT_TIME_COST,
    memory_cost: int = DEFAULT_MEMORY_COST,
    parallelism: int = DEFAULT_PARALLELISM,
) -> Path:
    """Encrypt a file or folder to the VeyraLock .vlock format."""
    source = ensure_input_path(input_path)
    destination = ensure_output_path(
        encrypted_output_path(source, output_path),
        overwrite=overwrite,
    )
    _ensure_distinct_paths(source, destination)

    if source.is_dir():
        plaintext = _build_directory_archive(source, compress=compress)
        is_directory = True
    elif source.is_file():
        plaintext = source.read_bytes()
        is_directory = False
    else:
        raise ValueError(f"Unsupported input path type: {source}")

    package = _encrypt_payload(
        plaintext,
        password,
        original_name=source.name,
        compress=compress,
        is_directory=is_directory,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
    )
    destination.write_bytes(package)
    return destination


def decrypt_file(
    input_path: str | Path,
    password: str | bytes,
    *,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Decrypt a .vlock file back to its original file or folder."""
    source = ensure_input_file(input_path)
    package = source.read_bytes()
    envelope, header = _decrypt_payload(package, password)

    effective_name = envelope.original_name or header.original_name
    destination = decrypted_output_path(source, effective_name, output_path)
    _ensure_distinct_paths(source, destination)

    if envelope.is_directory:
        return _extract_directory_archive(envelope.data, destination, overwrite=overwrite)

    destination = ensure_output_path(destination, overwrite=overwrite)
    destination.write_bytes(envelope.data)
    return destination


def verify_encrypted_file(
    input_path: str | Path,
    password: str | bytes,
    *,
    expected_name: str | None = None,
) -> VLockHeader:
    """Verify that an encrypted file is readable, authentic, and matches expectations."""
    source = ensure_input_file(input_path)
    package = source.read_bytes()
    envelope, header = _decrypt_payload(package, password)
    effective_name = envelope.original_name or header.original_name

    if expected_name is not None and effective_name != expected_name:
        raise VeyraLockError(
            "Encrypted file verification failed because the embedded original name "
            "did not match the source path."
        )

    return header
