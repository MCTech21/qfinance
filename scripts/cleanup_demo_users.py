#!/usr/bin/env python3
"""Cleanup demo users and ensure target admin user is active/admin.

Defaults to dry-run. Use --apply to execute changes.
"""

import argparse
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # optional dependency
    def load_dotenv(*_args, **_kwargs):
        return False


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / "backend" / ".env")

DEFAULT_TARGET_EMAIL = os.getenv("TARGET_ADMIN_EMAIL", "encargado.finanzas@quantumgrupo.mx")
DEFAULT_TARGET_USERNAME = os.getenv("TARGET_ADMIN_USERNAME", "MoisesFinanzas")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "qfinance")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove demo users and enforce target admin user")
    parser.add_argument("--apply", action="store_true", help="Apply changes. If omitted, run as dry-run")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode")
    parser.add_argument("--target-email", default=DEFAULT_TARGET_EMAIL, help="Real user email that must remain active/admin")
    parser.add_argument("--target-username", default=DEFAULT_TARGET_USERNAME, help="Real user name")
    parser.add_argument(
        "--target-password",
        default=os.getenv("TARGET_ADMIN_PASSWORD"),
        help="Password for user creation only (optional). If missing, a random password is generated and printed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        from pymongo import MongoClient
    except Exception as exc:
        raise SystemExit(f"pymongo is required for cleanup_demo_users.py: {exc}")

    try:
        import bcrypt
    except Exception as exc:
        raise SystemExit(f"bcrypt is required for cleanup_demo_users.py: {exc}")

    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    apply_changes = args.apply and not args.dry_run

    target_email = args.target_email.strip().lower()
    target_username = args.target_username.strip()

    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]

    demo_query = {
        "$and": [
            {"email": {"$regex": r"@finrealty\.com$", "$options": "i"}},
            {"email": {"$ne": target_email}},
        ]
    }

    demo_users = list(db.users.find(demo_query, {"_id": 0}))

    print(f"mode={'APPLY' if apply_changes else 'DRY-RUN'}")
    print(f"demo_users_found={len(demo_users)}")
    for user in demo_users:
        print(f" - {user.get('email')} ({user.get('id')}) active={user.get('is_active', True)}")

    deleted_count = 0
    deactivated_count = 0

    if apply_changes:
        for user in demo_users:
            user_id = user.get("id")
            try:
                result = db.users.delete_one({"id": user_id})
                if result.deleted_count:
                    deleted_count += 1
                    continue
                soft = db.users.update_one({"id": user_id}, {"$set": {"is_active": False, "is_demo": True}})
                if soft.modified_count:
                    deactivated_count += 1
            except Exception:
                soft = db.users.update_one({"id": user_id}, {"$set": {"is_active": False, "is_demo": True}})
                if soft.modified_count:
                    deactivated_count += 1

    target_user = db.users.find_one({"email": target_email}, {"_id": 0})

    if not target_user:
        generated_password = args.target_password or secrets.token_urlsafe(12)
        new_user = {
            "id": str(uuid.uuid4()),
            "email": target_email,
            "name": target_username,
            "role": "admin",
            "is_active": True,
            "is_demo": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "password_hash": hash_password(generated_password),
        }
        if apply_changes:
            db.users.insert_one(new_user)
        print(f"target_user_will_be_created={True}")
        if not args.target_password:
            print(f"generated_target_password={generated_password}")

    if apply_changes:
        db.users.update_one(
            {"email": target_email},
            {"$set": {"name": target_username, "role": "admin", "is_active": True, "is_demo": False}},
            upsert=True,
        )
        db.users.update_many(
            {"email": {"$ne": target_email}, "role": "admin"},
            {"$set": {"role": "finanzas"}},
        )

    final_target = db.users.find_one({"email": target_email}, {"_id": 0})
    print(f"demo_users_deleted={deleted_count}")
    print(f"demo_users_deactivated={deactivated_count}")
    if final_target:
        print(
            "target_user_status="
            f"email={final_target.get('email')} name={final_target.get('name')} "
            f"role={final_target.get('role')} active={final_target.get('is_active')} is_demo={final_target.get('is_demo')}"
        )
    else:
        print("target_user_status=NOT_FOUND")


if __name__ == "__main__":
    main()
