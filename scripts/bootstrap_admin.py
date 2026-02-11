#!/usr/bin/env python3
import argparse
import asyncio
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

DEFAULT_ADMIN_EMAIL = "encargado.finanzas@quantumgrupo.mx"
DEFAULT_ADMIN_USERNAME = "MoisesFinanzas"


def parse_args():
    parser = argparse.ArgumentParser(description="Bootstrap admin user in QFinance")
    parser.add_argument("--email", help="Admin email (fallback ADMIN_EMAIL env)")
    parser.add_argument("--username", help="Admin username/name (fallback ADMIN_USERNAME env)")
    parser.add_argument("--name", default=DEFAULT_ADMIN_USERNAME, help="Name for created user")
    parser.add_argument("--password-hash", help="Optional precomputed password hash for new user")
    parser.add_argument("--deactivate-demo-users", action="store_true", help="Deactivate demo users")
    return parser.parse_args()


async def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
    args = parse_args()

    email = args.email or os.getenv("ADMIN_EMAIL") or DEFAULT_ADMIN_EMAIL
    username = args.username or os.getenv("ADMIN_USERNAME") or DEFAULT_ADMIN_USERNAME

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    query_candidates = []
    if email:
        query_candidates.append({"email": email})
    if username:
        query_candidates.append({"name": username})

    user = None
    for query in query_candidates:
        user = await db.users.find_one(query, {"_id": 0})
        if user:
            break

    if user:
        await db.users.update_one(
            {"id": user["id"]},
            {
                "$set": {
                    "role": "admin",
                    "is_active": True,
                    "is_demo": False,
                    "email": user.get("email") or email,
                    "name": user.get("name") or username,
                }
            },
        )
        print(f"Updated existing user as admin: id={user['id']} email={user.get('email')} name={user.get('name')}")
    else:
        if not email:
            raise SystemExit("Cannot create admin without email. Provide --email or ADMIN_EMAIL")
        doc = {
            "id": str(uuid.uuid4()),
            "email": email,
            "name": username or args.name,
            "role": "admin",
            "is_active": True,
            "is_demo": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "password_hash": args.password_hash or "",
        }
        await db.users.insert_one(doc)
        print(f"Created new admin user: email={email} name={doc['name']}")

    if args.deactivate_demo_users:
        result = await db.users.update_many(
            {
                "is_demo": True,
                "email": {"$ne": email},
            },
            {"$set": {"is_active": False}},
        )
        print(f"Demo users deactivated: {result.modified_count}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
