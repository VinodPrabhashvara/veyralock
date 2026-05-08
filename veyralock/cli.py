"""Command-line interface for VeyraLock."""

from __future__ import annotations

import argparse
import getpass
import shutil
import sys
from pathlib import Path

from . import __version__
from .crypto import (
    InvalidPasswordOrCorruptFile,
    VeyraLockError,
    decrypt_file,
    encrypt_file,
    verify_encrypted_file,
)
from .fileformat import FileFormatError, unpack_header
from .password import check_password_strength
from .utils import (
    best_effort_delete_file,
    encrypted_output_path,
    ensure_input_file,
    ensure_input_path,
)


def _confirm(prompt: str, *, assume_yes: bool = False) -> bool:
    """Prompt the user for a yes/no answer."""
    if assume_yes:
        return True

    response = input(f"{prompt} [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def _read_encrypt_password() -> str:
    first = getpass.getpass("Enter password: ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        raise ValueError("Passwords do not match.")
    if not first:
        raise ValueError("Password must not be empty.")
    return first


def _read_decrypt_password() -> str:
    password = getpass.getpass("Enter password: ")
    if not password:
        raise ValueError("Password must not be empty.")
    return password


def _resolve_encrypt_output(input_path: str | Path, output_path: str | Path | None) -> Path:
    source = ensure_input_path(input_path)
    return encrypted_output_path(source, output_path)


def _resolve_decrypt_output(output_path: str | Path | None) -> Path | None:
    if output_path is None:
        return None
    return Path(output_path)


def _print_info(input_path: str | Path) -> None:
    source = ensure_input_file(input_path)
    try:
        header, _ = unpack_header(source.read_bytes())
    except FileFormatError as exc:
        raise VeyraLockError(str(exc)) from exc

    print(f"File: {source}")
    print(f"Format version: {header.version}")
    print(f"KDF: {header.kdf_name}")
    print(f"Salt size: {len(header.salt)} bytes")
    print(f"Nonce size: {len(header.nonce)} bytes")


def _maybe_confirm_overwrite(destination: Path, *, assume_yes: bool) -> bool:
    if not destination.exists():
        return True
    return _confirm(f"Output file exists: {destination}. Overwrite it?", assume_yes=assume_yes)


def _delete_original_path(source: Path) -> str:
    """Delete the original input after successful encryption and verification."""
    if source.is_dir():
        shutil.rmtree(source)
        return "Deleted original folder after encrypted output verification."

    best_effort_delete_file(source)
    return (
        "Deleted original file after encrypted output verification. "
        "Best-effort overwrite was attempted once before deletion."
    )


def _handle_encrypt(args: argparse.Namespace) -> int:
    password = _read_encrypt_password()
    strength = check_password_strength(password)

    for warning in strength.warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    if strength.is_dangerously_short:
        print("Encryption cancelled.", file=sys.stderr)
        return 1

    if strength.warnings and not _confirm(
        "Continue with this password?",
        assume_yes=args.yes,
    ):
        print("Encryption cancelled.", file=sys.stderr)
        return 1

    source = ensure_input_path(args.path)
    destination = _resolve_encrypt_output(source, args.output)
    if not _maybe_confirm_overwrite(destination, assume_yes=args.yes):
        print("Encryption cancelled.", file=sys.stderr)
        return 1

    destination = encrypt_file(
        source,
        password,
        output_path=destination,
        compress=not args.no_compress,
        overwrite=True,
    )
    verify_encrypted_file(destination, password, expected_name=source.name)
    print(f"Success: encrypted '{source}' to '{destination}'.")

    if args.delete_original:
        if _confirm(
            f"Delete original path '{source}' now that encryption succeeded?",
            assume_yes=args.yes,
        ):
            message = _delete_original_path(source)
            print(f"{message} Path: '{source}'.")
        else:
            print("Original path was kept.")

    return 0


def _handle_decrypt(args: argparse.Namespace) -> int:
    password = _read_decrypt_password()
    source = ensure_input_file(args.path)
    destination = _resolve_decrypt_output(args.output)
    if destination is not None and not _maybe_confirm_overwrite(destination, assume_yes=args.yes):
        print("Decryption cancelled.", file=sys.stderr)
        return 1

    destination = decrypt_file(
        source,
        password,
        output_path=destination,
        overwrite=True,
    )
    print(f"Success: decrypted '{source}' to '{destination}'.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veyralock",
        description="Secure cross-platform file encryption using AES-256-GCM and Argon2id.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    encrypt_parser = subparsers.add_parser("encrypt", help="Encrypt a file or folder.")
    encrypt_parser.add_argument("path", help="Path to the source file or folder.")
    encrypt_parser.add_argument(
        "-o",
        "--output",
        help="Optional output path. Defaults to <input>.vlock.",
    )
    encrypt_parser.add_argument(
        "--delete-original",
        action="store_true",
        help="Delete the original file or folder after successful encryption.",
    )
    encrypt_parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Disable pre-encryption compression.",
    )
    encrypt_parser.add_argument(
        "--yes",
        action="store_true",
        help="Assume yes for confirmations, including overwrite and delete prompts.",
    )

    decrypt_parser = subparsers.add_parser("decrypt", help="Decrypt a .vlock file.")
    decrypt_parser.add_argument("path", help="Path to the encrypted .vlock file.")
    decrypt_parser.add_argument(
        "-o",
        "--output",
        help="Optional output path. Defaults to the embedded original filename.",
    )
    decrypt_parser.add_argument(
        "--yes",
        action="store_true",
        help="Assume yes for confirmations, including overwrite prompts.",
    )

    info_parser = subparsers.add_parser(
        "info",
        help="Show safe metadata from an encrypted .vlock file.",
    )
    info_parser.add_argument("path", help="Path to the encrypted .vlock file.")

    return parser


def _run_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.command == "encrypt":
        return _handle_encrypt(args)
    if args.command == "decrypt":
        return _handle_decrypt(args)
    if args.command == "info":
        _print_info(args.path)
        return 0

    parser.error("Unknown command.")
    return 2


def _print_error(message: str, *, exit_code: int = 1) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return _run_command(args, parser)
    except (FileNotFoundError, FileExistsError, ValueError, OSError) as exc:
        return _print_error(str(exc), exit_code=1)
    except InvalidPasswordOrCorruptFile as exc:
        return _print_error(str(exc), exit_code=2)
    except VeyraLockError as exc:
        return _print_error(str(exc), exit_code=1)
    except KeyboardInterrupt:
        return _print_error("Operation cancelled by user.", exit_code=130)


if __name__ == "__main__":
    raise SystemExit(main())
