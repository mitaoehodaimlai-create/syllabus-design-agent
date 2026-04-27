"""
STEP 7 — Seed Script: Create First Admin User
------------------------------------------------
Run ONCE after first deploy to bootstrap an admin account.
Never expose an open /register?role=admin endpoint in production.

Usage:
  python create_admin.py
  python create_admin.py --username admin --email admin@college.edu --password Secret123
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from api.database import init_db, create_user, get_user_by_username
from api.auth import hash_password


def main():
    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--email",    default="admin@syllabus.local")
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    init_db()

    # Check if already exists
    existing = get_user_by_username(args.username)
    if existing:
        print(f"User '{args.username}' already exists with role: {existing['role']}")
        sys.exit(0)

    password = args.password
    if not password:
        import getpass
        password = getpass.getpass(f"Password for '{args.username}': ")

    if len(password) < 8:
        print("Error: password must be at least 8 characters")
        sys.exit(1)

    user = create_user(
        username=args.username,
        email=args.email,
        hashed_password=hash_password(password),
        role="admin",
    )
    print(f"Admin created: id={user['id']}  username={user['username']}  role={user['role']}")


if __name__ == "__main__":
    main()
