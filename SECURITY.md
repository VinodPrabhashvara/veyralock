# Security Policy

## Supported Versions

The following versions are supported for security fixes:

- the latest `main` branch
- the latest tagged release

Older releases may not receive security updates.

## Reporting a Vulnerability

Please do not publish serious vulnerabilities in public issues before reporting them responsibly.

When reporting a vulnerability, include:

- a clear description of the issue
- affected version or commit
- reproduction steps or proof of concept
- impact assessment
- environment details that matter for reproduction

If you are unsure whether an issue is security-sensitive, treat it as private first.

## Security Expectations

VeyraLock aims to use well-established cryptographic building blocks and conservative failure behavior:

- AES-256-GCM for authenticated encryption
- Argon2id for password-based key derivation
- authenticated decryption failure for wrong passwords and tampered files
- no password logging by design

Security review, dependency maintenance, and safe operational use still matter. Users should validate the tool against their own threat model before production use.

## Known Limitations

- Weak passwords can be brute-forced.
- Secure delete is best-effort only.
- Malware on the user device can steal passwords before encryption or decryption.
- Losing the password means the encrypted data cannot be recovered.
