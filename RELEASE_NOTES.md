# VeyraLock 1.0.0 Release Notes

VeyraLock 1.0.0 is the first public release of the project.

## What is Included

- File and folder encryption
- File and folder decryption
- AES-256-GCM authenticated encryption
- Argon2id password-based key derivation
- Encrypted filename metadata
- Wrong-password detection
- Tamper detection
- Desktop GUI and CLI workflows
- One Windows EXE that supports both GUI and CLI

## Download Instructions

- Source users can clone the repository and install with `pip install -e .`
- Windows users can build or download `VeyraLock.exe` when release artifacts are provided

## Windows EXE Usage

Double-click `VeyraLock.exe` to open the GUI.

Command-line usage:

```powershell
.\dist\VeyraLock.exe --gui
.\dist\VeyraLock.exe --help
.\dist\VeyraLock.exe encrypt file.pdf
.\dist\VeyraLock.exe decrypt file.pdf.vlock
```

## CLI Examples

```bash
veyralock encrypt report.pdf
veyralock encrypt project-folder
veyralock decrypt report.pdf.vlock
veyralock info report.pdf.vlock
```

## GUI Usage

- Use the Encrypt tab for new encrypted containers
- Use the Decrypt tab to restore `.vlock` files
- The Encrypt tab requires password confirmation
- The Decrypt tab requires password only

## Security Warnings

- Password strength directly affects real-world protection.
- Weak passwords can be brute-forced.
- Forgotten passwords cannot be recovered.
- Best-effort delete is not guaranteed to securely erase original data on all storage types.
