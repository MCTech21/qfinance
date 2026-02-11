#!/usr/bin/env python3
import argparse
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio


def parse_args():
    parser = argparse.ArgumentParser(description="Bootstrap admin user in QFinance")
    parser.add_argument("--email", help="Admin email (fallback ADMIN_EMAIL env)")
    parser.add_argument("--name", default="Bootstrap Admin", help="Name for created user")
    parser.add_argument("--password-hash", help="Optional precomputed password hash for new user")
    parser.add_argument("--deactivate-demo-users", action="store_true", help="Deactivate demo users")
    return parser.parse_args()


async def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
    args = parse_args()
    email = args.email or os.getenv("ADMIN_EMAIL")
    if not email:
        raise SystemExit("Provide --email or ADMIN_EMAIL")

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"role": "admin", "is_active": True, "is_demo": False}},
        )
        print(f"Updated existing user as admin: {email}")
    else:
        doc = {
            "id": str(uuid.uuid4()),
            "email": email,
            "name": args.name,
            "role": "admin",
            "is_active": True,
            "is_demo": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "password_hash": args.password_hash or "",
        }
        await db.users.insert_one(doc)
        print(f"Created new admin user: {email}")

    if args.deactivate_demo_users:
        result = await db.users.update_many(
            {"is_demo": True, "email": {"$ne": email}},
            {"$set": {"is_active": False}},
        )
        print(f"Demo users deactivated: {result.modified_count}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
