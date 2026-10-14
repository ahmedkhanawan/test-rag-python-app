"""Print an Argon2id hash for ADMIN_PASSWORD_HASH: `uv run python -m scripts.hash_password`."""

import getpass

from app.core.security import hash_password

if __name__ == "__main__":
    password = getpass.getpass("Admin password: ")
    if getpass.getpass("Repeat password: ") != password or not password:
        raise SystemExit("Passwords did not match (or were empty).")
    print(hash_password(password))
