import base64
import hashlib
import hmac
import secrets


HASH_ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 260_000
SALT_BYTES = 16


def _b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def hash_password(password: str, iterations: int = DEFAULT_ITERATIONS) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return "$".join(
        [
            HASH_ALGORITHM,
            str(iterations),
            _b64encode(salt),
            _b64encode(derived_key),
        ]
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, hash_text = password_hash.split("$", 3)
        if algorithm != HASH_ALGORITHM:
            return False

        iterations = int(iterations_text)
        salt = _b64decode(salt_text)
        expected_hash = _b64decode(hash_text)
    except (ValueError, TypeError):
        return False

    actual_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual_hash, expected_hash)
