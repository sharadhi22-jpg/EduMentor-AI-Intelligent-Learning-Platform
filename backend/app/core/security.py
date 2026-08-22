from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt

from app.core.config import settings


def hash_password(plain_password: str) -> str:
    """Securely hash a password using bcrypt before database insertion."""
    password_bytes = plain_password.encode("utf-8")
    # gensalt default rounds is 12, which is secure and fast
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that a plaintext password matches the stored bcrypt hash."""
    password_bytes = plain_password.encode("utf-8")
    try:
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    """
    Create a signed JSON Web Token (JWT) with user details.
    `subject` typically contains the user ID.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode = {"sub": subject, "exp": expire}
    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """
    Decode, verify signature and expiry of a JWT token.
    Returns None if signature is invalid or token has expired.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
