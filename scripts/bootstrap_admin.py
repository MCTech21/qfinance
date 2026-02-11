#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

DEFAULT_ADMIN_EMAIL = "encargado.finanzas@quantumgrupo.mx"
DEFAULT_ADMIN_USERNAME = "MoisesFinanzas"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8088/api"
DEFAULT_BOOTSTRAP_EMAIL = "admin@finrealty.com"
DEFAULT_BOOTSTRAP_PASSWORD = "admin123"


def parse_args():
    parser = argparse.ArgumentParser(description="Bootstrap admin user in QFinance")
    parser.add_argument("--email", help="Target admin email")
    parser.add_argument("--username", help="Target admin username/name")
    parser.add_argument("--name", default=DEFAULT_ADMIN_USERNAME, help="Name for created user")
    parser.add_argument("--password-hash", help="DB mode only: password_hash for created user")
    parser.add_argument("--new-password", default="admin123", help="API mode: password for created target user")
    parser.add_argument("--deactivate-demo-users", action="store_true", help="Deactivate demo users")
    parser.add_argument("--mode", choices=["auto", "db", "api"], default="auto", help="Execution mode")
    parser.add_argument("--api-base-url", default=os.getenv("QFINANCE_API_BASE_URL", DEFAULT_API_BASE_URL), help="API base URL")
    parser.add_argument("--bootstrap-email", default=os.getenv("BOOTSTRAP_ADMIN_EMAIL", DEFAULT_BOOTSTRAP_EMAIL), help="Existing admin email for API auth")
    parser.add_argument("--bootstrap-password", default=os.getenv("BOOTSTRAP_ADMIN_PASSWORD", DEFAULT_BOOTSTRAP_PASSWORD), help="Existing admin password for API auth")
    return parser.parse_args()


def load_env_file(path: str):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def request_json(method: str, url: str, payload=None, token: str = None):
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"detail": body or str(e)}
        return e.code, parsed
    except urllib.error.URLError as e:
        return 0, {"detail": f"Cannot reach API endpoint: {url} ({e.reason})"}


def run_api_mode(args, email, username):
    base = args.api_base_url.rstrip("/")

    login_status, login_data = request_json(
        "POST",
        f"{base}/auth/login",
        {"email": args.bootstrap_email, "password": args.bootstrap_password},
    )
    if login_status != 200:
        raise SystemExit(f"API login failed ({login_status}): {login_data}")

    token = login_data.get("access_token")
    if not token:
        raise SystemExit("API login did not return access_token")

    status, users = request_json("GET", f"{base}/users", token=token)
    if status != 200:
        raise SystemExit(f"Cannot list users ({status}): {users}")

    target = None
    for user in users:
        if email and user.get("email") == email:
            target = user
            break
        if username and user.get("name") == username:
            target = user
            break

    if target is None:
        register_payload = {
            "email": email,
            "name": username or args.name,
            "role": "admin",
            "password": args.new_password,
        }
        status, created = request_json("POST", f"{base}/auth/register", register_payload)
        if status not in (200, 201):
            raise SystemExit(f"Cannot create target user ({status}): {created}")
        target = created
        print(f"Created target user via API: email={target.get('email')} name={target.get('name')}")

    status, _ = request_json(
        "PUT",
        f"{base}/users/{target['id']}",
        {"role": "admin", "is_active": True},
        token=token,
    )
    if status != 200:
        raise SystemExit(f"Cannot promote target user ({status})")
    print(f"Updated existing user as admin via API: id={target['id']} email={target.get('email')} name={target.get('name')}")

    if args.deactivate_demo_users:
        changed = 0
        for user in users:
            if user.get("id") == target.get("id"):
                continue
            if user.get("is_demo") is True:
                status, _ = request_json("PUT", f"{base}/users/{user['id']}", {"is_active": False}, token=token)
                if status == 200:
                    changed += 1
        print(f"Demo users deactivated (API mode): {changed}")


def run_db_mode(args, email, username):
    from motor.motor_asyncio import AsyncIOMotorClient  # optional dependency
    import asyncio

    async def _run():
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
                {"$set": {"role": "admin", "is_active": True, "is_demo": False}},
            )
            print(f"Updated existing user as admin: id={user['id']} email={user.get('email')} name={user.get('name')}")
        else:
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
                {"is_demo": True, "email": {"$ne": email}},
                {"$set": {"is_active": False}},
            )
            print(f"Demo users deactivated: {result.modified_count}")

        client.close()

    asyncio.run(_run())


def main():
    args = parse_args()

    env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
    load_env_file(env_path)

    email = args.email or os.getenv("ADMIN_EMAIL") or DEFAULT_ADMIN_EMAIL
    username = args.username or os.getenv("ADMIN_USERNAME") or DEFAULT_ADMIN_USERNAME

    if args.mode == "api":
        run_api_mode(args, email, username)
        return

    if args.mode == "db":
        run_db_mode(args, email, username)
        return

    # auto mode
    try:
        import motor  # noqa: F401
        if os.getenv("MONGO_URL") and os.getenv("DB_NAME"):
            run_db_mode(args, email, username)
            return
    except ModuleNotFoundError:
        pass

    run_api_mode(args, email, username)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
