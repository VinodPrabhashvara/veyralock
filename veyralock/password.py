"""Password handling and secure key derivation."""

from __future__ import annotations

import os
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw

KEY_SIZE = 32
SALT_SIZE = 16
DEFAULT_TIME_COST = 3
DEFAULT_MEMORY_COST = 65536
DEFAULT_PARALLELISM = 4
MINIMUM_PASSWORD_LENGTH = 8
RECOMMENDED_PASSWORD_LENGTH = 12
STRONG_PASSWORD_LENGTH = 16
COMMON_WEAK_PASSWORDS = frozenset(
    {
        "password",
        "password123",
        "12345678",
        "qwerty",
        "admin",
        "iloveyou",
    }
)


@dataclass(frozen=True)
class PasswordStrength:
    """Human-friendly password strength assessment."""

    warnings: tuple[str, ...]
    is_dangerously_short: bool
    meets_recommended_length: bool
    meets_strong_length: bool

    @property
    def is_acceptable(self) -> bool:
        """Whether the password clears the minimum safety bar."""
        return not self.is_dangerously_short


def check_password_strength(password: str) -> PasswordStrength:
    """Assess password strength without sending or logging the password."""
    if not isinstance(password, str):
        raise TypeError("Password strength checks require a string password.")

    normalized = password.strip().lower()
    warnings: list[str] = []
    length = len(password)

    if length < MINIMUM_PASSWORD_LENGTH:
        warnings.append(
            "Password is dangerously short. Use at least 8 characters before continuing."
        )
    elif length < RECOMMENDED_PASSWORD_LENGTH:
        warnings.append(
            "Password is shorter than the recommended minimum of 12 characters."
        )
    elif length < STRONG_PASSWORD_LENGTH:
        warnings.append(
            "Password meets the minimum recommendation, but 16+ characters is stronger."
        )

    if normalized in COMMON_WEAK_PASSWORDS:
        warnings.append(
            "Password matches a very common weak password and is easy to guess."
        )

    diversity_score = sum(
        (
            any(char.islower() for char in password),
            any(char.isupper() for char in password),
            any(char.isdigit() for char in password),
            any(not char.isalnum() for char in password),
        )
    )
    if length >= MINIMUM_PASSWORD_LENGTH and diversity_score < 2:
        warnings.append(
            "Password uses very limited character variety. Mix letters, numbers, or symbols."
        )

    return PasswordStrength(
        warnings=tuple(warnings),
        is_dangerously_short=length < MINIMUM_PASSWORD_LENGTH,
        meets_recommended_length=length >= RECOMMENDED_PASSWORD_LENGTH,
        meets_strong_length=length >= STRONG_PASSWORD_LENGTH,
    )


def normalize_password(password: str | bytes) -> bytes:
    """Convert a password value to bytes for KDF input."""
    if isinstance(password, bytes):
        password_bytes = password
    elif isinstance(password, str):
        password_bytes = password.encode("utf-8")
    else:
        raise TypeError("Password must be a string or bytes.")

    if not password_bytes:
        raise ValueError("Password must not be empty.")

    return password_bytes


def generate_salt() -> bytes:
    """Generate a cryptographically secure random salt."""
    return os.urandom(SALT_SIZE)


def derive_key(
    password: str | bytes,
    salt: bytes,
    *,
    time_cost: int = DEFAULT_TIME_COST,
    memory_cost: int = DEFAULT_MEMORY_COST,
    parallelism: int = DEFAULT_PARALLELISM,
) -> bytes:
    """Derive a 256-bit AES key from a password using Argon2id."""
    password_bytes = normalize_password(password)

    if len(salt) != SALT_SIZE:
        raise ValueError(f"Salt must be {SALT_SIZE} bytes.")
    if time_cost < 1:
        raise ValueError("Argon2 time cost must be at least 1.")
    if memory_cost < 8:
        raise ValueError("Argon2 memory cost must be at least 8 KiB.")
    if parallelism < 1:
        raise ValueError("Argon2 parallelism must be at least 1.")

    return hash_secret_raw(
        secret=password_bytes,
        salt=salt,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=KEY_SIZE,
        type=Type.ID,
    )
