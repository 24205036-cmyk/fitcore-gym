from werkzeug.security import generate_password_hash, check_password_hash

def hash_password(password: str) -> str:
    """Hashes a plaintext password securely using werkzeug."""
    return generate_password_hash(password, method='scrypt')

def verify_password(hashed_password: str, password: str) -> bool:
    """Verifies a plaintext password against the stored hash."""
    if not hashed_password or not password:
        return False
    return check_password_hash(hashed_password, password)
