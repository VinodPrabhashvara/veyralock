# VeyraLock

**VeyraLock** is a cross-platform file and folder encryption tool with a clean desktop GUI and CLI workflow.  
It uses **AES-256-GCM**, **Argon2id**, encrypted metadata, wrong-password detection, and tamper detection.

> VeyraLock is designed to make unauthorized decryption computationally infeasible when a strong password is used.

---

## Features

- Encrypt and decrypt any file type
- Encrypt and decrypt folders
- AES-256-GCM authenticated encryption
- Argon2id password-based key derivation
- Random salt for every encryption
- Random nonce for every encryption
- Encrypted original filename metadata
- Wrong-password detection
- Tamper detection
- Clean PySide6 desktop GUI
- Command-line interface
- One Windows EXE launcher
- Custom VeyraLock icon
- Best-effort delete-original option
- Cross-platform source support: Windows, Linux, and macOS

---

## Screenshots

Place screenshots here:

```text
docs/screenshots/main-window.png
docs/screenshots/encrypt-tab.png
docs/screenshots/decrypt-tab.png
```

Example:

```markdown
![VeyraLock Main Window](docs/screenshots/main-window.png)
```

---

## Security Design

VeyraLock uses established cryptographic primitives instead of custom encryption algorithms.

### Encryption

VeyraLock uses:

- **AES-256-GCM** for confidentiality and authenticity
- **Argon2id** for password-based key derivation
- A fresh random salt for every encryption
- A fresh random nonce for every encryption
- Authenticated metadata to detect tampering

### Metadata Protection

The original filename is not stored in plain text in the public `.vlock` header.  
Instead, sensitive metadata such as the real filename is stored inside the encrypted payload.

This helps reduce metadata leakage when encrypted files are stored, uploaded, or shared.

---

## What VeyraLock Protects Against

VeyraLock is designed to protect against:

- Offline attempts to decrypt `.vlock` files without the correct password
- Silent modification of encrypted file contents
- Silent tampering with protected metadata
- Accidental exposure of original filenames in public headers
- Untrusted storage, transfer, backup, and upload environments

---

## What VeyraLock Does Not Protect Against

VeyraLock does **not** protect against:

- Weak passwords that can be guessed or brute-forced
- Malware, spyware, or keyloggers on your device
- Password reuse across different accounts or tools
- Recovery of forgotten passwords
- A device that is already compromised
- Guaranteed forensic erasure of deleted files

If you forget your password, VeyraLock cannot recover your encrypted files.

---

## Installation from Source

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/veyralock.git
cd veyralock
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
pip install -e .
```

---

## GUI Usage

Launch the GUI from source:

```bash
python -m veyralock.gui
```

Or, after installing the package:

```bash
veyralock-gui
```

### GUI behavior

- **Encrypt tab**
  - Requires password
  - Requires password confirmation
  - Supports file and folder encryption

- **Decrypt tab**
  - Requires only one password
  - Restores encrypted files or folders
  - Uses encrypted metadata to restore the original name when possible

---

## CLI Usage

Show help:

```bash
veyralock --help
```

Encrypt a file:

```bash
veyralock encrypt report.pdf
```

Encrypt a folder:

```bash
veyralock encrypt project-folder
```

Decrypt a file:

```bash
veyralock decrypt report.pdf.vlock
```

Show safe public metadata:

```bash
veyralock info report.pdf.vlock
```

Use a custom output path:

```bash
veyralock encrypt report.pdf --output report.pdf.vlock
veyralock decrypt report.pdf.vlock --output restored-report.pdf
```

Delete the original after successful encryption:

```bash
veyralock encrypt secrets.txt --delete-original
```

If the console command is not available, use:

```bash
python -m veyralock.cli encrypt report.pdf
python -m veyralock.cli decrypt report.pdf.vlock
```

---

## Windows EXE Usage

The Windows release provides one executable:

```text
VeyraLock.exe
```

Double-click:

```text
VeyraLock.exe
```

This opens the GUI.

CLI examples:

```powershell
.\VeyraLock.exe --help
.\VeyraLock.exe --gui
.\VeyraLock.exe encrypt file.pdf
.\VeyraLock.exe decrypt file.pdf.vlock
```

For the most reliable CLI output on Windows, use the source-installed CLI:

```powershell
python -m veyralock.cli --help
```

---

## Building Windows EXE

Build the executable:

```powershell
.\scripts\build_windows.ps1
```

Output:

```text
dist\VeyraLock.exe
```

Test the executable:

```powershell
.\dist\VeyraLock.exe --gui
.\dist\VeyraLock.exe --help
```

The Windows build is configured so that double-clicking the EXE opens the GUI without showing a terminal window.

---

## File Format Overview

VeyraLock encrypted files use the `.vlock` extension.

A `.vlock` container includes:

```text
Magic header
Format version
KDF identifier
Salt
Nonce
Authenticated encrypted payload
```

The encrypted payload contains protected metadata such as:

```text
Original filename
File/folder information
Encrypted content
Integrity-protected data
```

The public header does not expose the real original filename.

---

## Password Safety

Password strength directly affects protection.

Recommended password rules:

- Use a unique password
- Use at least 12 characters
- Prefer 16 or more characters
- Avoid common words and reused passwords
- Store important passwords safely

VeyraLock cannot recover forgotten passwords.

---

## Secure Delete Warning

The delete-original option is **best-effort only**.

Secure deletion is not guaranteed on:

- SSDs
- Cloud-synced folders
- Journaling filesystems
- Storage systems with snapshots
- Drives with wear leveling

For highly sensitive files, use full-disk encryption and secure operational practices.

---

## Development Setup

Install development dependencies:

```bash
pip install -r requirements.txt
pip install -e .[dev]
```

Run tests:

```bash
python -m pytest
```

Run compile checks:

```bash
python -m py_compile veyralock_entry.py veyralock/gui.py veyralock/cli.py veyralock/crypto.py
```

---

## Project Structure

```text
veyralock/
├── .github/
├── assets/
│   └── veyralock.ico
├── docs/
│   └── screenshots/
├── scripts/
│   └── build_windows.ps1
├── tests/
├── veyralock/
│   ├── cli.py
│   ├── crypto.py
│   ├── fileformat.py
│   ├── gui.py
│   ├── password.py
│   └── utils.py
├── veyralock_entry.py
├── README.md
├── SECURITY.md
├── CHANGELOG.md
├── RELEASE_NOTES.md
├── pyproject.toml
└── requirements.txt
```

---

## GitHub Release Notes

For release details, see:

```text
RELEASE_NOTES.md
```

Recommended release asset:

```text
dist\VeyraLock.exe
```

Do not commit the EXE into the repository. Upload it as a GitHub Release asset.

---

## Security Policy

Please report security issues responsibly.

See:

```text
SECURITY.md
```

Do not publicly disclose serious vulnerabilities before giving maintainers time to investigate and fix them.

---

## License

VeyraLock is released under the MIT License.

See:

```text
LICENSE
```

---

## Disclaimer

VeyraLock is security software, but no software can guarantee absolute protection.

Use strong passwords, keep your system clean from malware, and maintain secure backups.
