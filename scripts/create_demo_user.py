import argparse
import sys
from pathlib import Path

from sqlalchemy import text


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.database.session import SessionLocal  # noqa: E402
from app.utils.password import hash_password  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a local demo user.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    password_hash = hash_password(args.password)
    query = text(
        """
        INSERT INTO users (username, password_hash)
        VALUES (:username, :password_hash)
        ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash)
        """
    )

    with SessionLocal() as db:
        db.execute(query, {"username": args.username, "password_hash": password_hash})
        db.commit()

    print(f"User '{args.username}' is ready.")


if __name__ == "__main__":
    main()
