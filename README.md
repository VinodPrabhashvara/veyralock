# VeyraLock

VeyraLock is a cross-platform file and folder encryption tool using AES-256-GCM, Argon2id, encrypted metadata, tamper detection, and a clean GUI/CLI workflow.

VeyraLock is designed to make unauthorized decryption computationally infeasible when a strong password is used.

## Features

- AES-256-GCM authenticated encryption
- Argon2id password-based key derivation
- Random salt for every encryption
- Random nonce for every encryption
- Encrypted original filename metadata inside the protected payload
- Wrong-password detection
- Tamper detection
- File encryption and decryption
- Folder encryption and decryption
- Cross-platform CLI workflow
- Cross-platform PySide6 desktop GUI
- One Windows EXE that supports both GUI and CLI

## Screenshots

Place GUI screenshots in `docs/screenshots/`.

Suggested filenames:

- `docs/screenshots/main-window.png`
- `docs/screenshots/encrypt-tab.png`
- `docs/screenshots/decrypt-tab.png`

## Security Design

VeyraLock uses established cryptographic primitives rather than custom cryptography.

- Encryption uses AES-256-GCM for confidentiality and authenticity.
- Password-based keys are derived with Argon2id.
- A fresh random salt is generated for each encryption operation.
- A fresh random nonce is generated for each encryption operation.
- Public container metadata is authenticated, and the real original filename is stored inside the encrypted payload.
- Wrong passwords fail closed during authenticated decryption.
- Modified encrypted files are rejected during authenticated decryption.
- Folder encryption preserves directory structure by encrypting an archive representation as one `.vlock` file.

## What VeyraLock Protects Against

- Offline attempts to decrypt a `.vlock` file without the correct password
- Silent tampering with encrypted content
- Silent tampering with protected metadata
- Accidental exposure of original filenames in public container headers
- Common operational use cases where encrypted files are copied, uploaded, backed up, or transferred through untrusted storage

## What VeyraLock Does Not Protect Against

- Malware, spyware, or keyloggers on the device where the password is entered
- Weak passwords that can be guessed or brute-forced
- Password reuse across multiple services or tools
- Recovery of forgotten passwords
- Guaranteed forensic erasure of deleted originals
- A system that is already compromised before or during encryption or decryption

## Installation from Source

Create and activate a virtual environment if you want an isolated setup:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies and the package:

```bash
pip install -r requirements.txt
pip install -e .
```

## CLI Usage

Show the installed version:

```bash
veyralock --version
```

Encrypt a file:

```bash
veyralock encrypt report.pdf
```

Encrypt a folder:

```bash
veyralock encrypt project-folder
```

Decrypt an encrypted container:

```bash
veyralock decrypt report.pdf.vlock
```

Show safe metadata only:

```bash
veyralock info report.pdf.vlock
```

Set an explicit output path:

```bash
veyralock encrypt report.pdf --output report.pdf.vlock
veyralock decrypt report.pdf.vlock --output restored-report.pdf
```

Delete the original after successful encryption:

```bash
veyralock encrypt secrets.txt --delete-original
```

If the console script is not on your `PATH`, run:

```bash
python -m veyralock.cli encrypt report.pdf
python -m veyralock.cli decrypt report.pdf.vlock
```

## GUI Usage

Launch the desktop application:

```bash
veyralock-gui
```

Or run it directly from source:

```bash
python -m veyralock.gui
```

GUI behavior:

- The Encrypt tab uses `Password` and `Confirm password`.
- The Decrypt tab uses `Password` only.
- Folder inputs are supported from the Encrypt tab.
- The status panel shows progress and operation results.

## Building Windows EXE

Build the combined Windows executable with:

```powershell
.\scripts\build_windows.ps1
```

Output:

```text
dist\VeyraLock.exe
```

Test the built executable with:

```powershell
.\dist\VeyraLock.exe --gui
.\dist\VeyraLock.exe --help
.\dist\VeyraLock.exe encrypt file.pdf
.\dist\VeyraLock.exe decrypt file.pdf.vlock
```

Double-clicking `VeyraLock.exe` opens the GUI. Running it with CLI arguments uses the command-line interface.

The Windows build is optimized so double-clicking opens the GUI without a terminal window.

For the most reliable CLI output on Windows, use the source-installed CLI directly:

```powershell
python -m veyralock.cli --help
```

## File Format Overview

Each `.vlock` container includes:

- magic header
- format version
- KDF identifier
- salt
- nonce
- authenticated encrypted payload

The payload contains the real original filename metadata in encrypted form. This reduces metadata leakage while keeping safe public format identification.

## Password Safety

- Password strength has a direct impact on real-world protection.
- Weak passwords may be guessed or brute-forced.
- Use a unique passphrase of at least 12 characters.
- A length of 16 or more characters is strongly recommended.
- Forgotten passwords cannot be recovered by the application.

## Secure Delete Warning

If you choose delete-after-encryption behavior, VeyraLock performs best-effort deletion only.

This is not guaranteed to securely erase data on SSDs, cloud-synced folders, journaling filesystems, or storage layers with snapshots and wear leveling.

## Development Setup

Install the project in editable mode:

```bash
pip install -r requirements.txt
pip install -e .
```

Optional development tools from `pyproject.toml`:

```bash
pip install -e .[dev]
```

## Running Tests

Run the full test suite:

```bash
python -m pytest
```

Run a compile smoke check:

```bash
python -m py_compile veyralock_entry.py veyralock/gui.py veyralock/cli.py veyralock/crypto.py
```

## GitHub Release Notes

For `v1.0.0`, see [RELEASE_NOTES.md](RELEASE_NOTES.md).

When publishing releases:

- attach the Windows EXE if you are distributing binaries
- include hashes if you publish standalone artifacts
- mention the supported Python versions and operating systems
- remind users that password strength determines practical resistance to attack

## Security Policy

See [SECURITY.md](SECURITY.md) for coordinated vulnerability reporting guidance and supported versions.

## License

VeyraLock is released under the MIT License. See [LICENSE](LICENSE) for details.
