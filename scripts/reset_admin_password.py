#!/usr/bin/env python3
"""Reset password for an existing user using admin API or DB mode.

Default mode is dry-run; pass --apply to execute updates.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_TARGET_EMAIL = os.getenv("TARGET_ADMIN_EMAIL", "encargado.finanzas@quantumgrupo.mx")
DEFAULT_TARGET_USERNAME = os.getenv("TARGET_ADMIN_USERNAME", "MoisesFinanzas")
DEFAULT_NEW_PASSWORD = os.getenv("TARGET_ADMIN_NEW_PASSWORD", "MoisesAdmin2026!")
DEFAULT_API_BASE_URL = os.getenv("QFINANCE_API_BASE_URL", "http://127.0.0.1:8088/api")
DEFAULT_BOOTSTRAP_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@finrealty.com")
DEFAULT_BOOTSTRAP_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin123")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset password for target user")
    parser.add_argument("--mode", choices=["api", "db", "auto"], default="auto")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    parser.add_argument("--email", default=DEFAULT_TARGET_EMAIL, help="Target user email")
    parser.add_argument("--username", default=DEFAULT_TARGET_USERNAME, help="Target user name")
    parser.add_argument("--new-password", default=DEFAULT_NEW_PASSWORD, help="New plain password")

    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL, help="Base API URL, e.g. http://host:8088/api")
    parser.add_argument("--bootstrap-email", default=DEFAULT_BOOTSTRAP_EMAIL, help="Bootstrap admin email")
    parser.add_argument("--bootstrap-password", default=DEFAULT_BOOTSTRAP_PASSWORD, help="Bootstrap admin password")

    parser.add_argument("--mongo-url", default=os.getenv("MONGO_URL", "mongodb://localhost:27017"), help="Mongo URL for DB mode")
    parser.add_argument("--db-name", default=os.getenv("DB_NAME", "qfinance"), help="Mongo DB name")
    return parser.parse_args()


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
            return resp.status, json.loads(body) if body else {}, url
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"detail": body or str(e)}
        return e.code, parsed, url
    except urllib.error.URLError as e:
        return 0, {"detail": f"Cannot reach API endpoint: {url} ({e.reason})"}, url


def run_api_mode(args: argparse.Namespace) -> int:
    base = args.api_base_url.rstrip("/")

    status, login_data, url = request_json(
        "POST",
        f"{base}/auth/login",
        {"email": args.bootstrap_email, "password": args.bootstrap_password},
    )
    if status != 200:
        print(f"[ERROR] API login failed ({status}) url={url}: {login_data}", file=sys.stderr)
        return 1

    token = login_data.get("access_token")
    if not token:
        print(f"[ERROR] API login did not return access_token url={url}", file=sys.stderr)
        return 1

    query = urllib.parse.urlencode({"email": args.email, "username": args.username, "include_inactive": "true"})
    status, users, url = request_json("GET", f"{base}/admin/users?{query}", token=token)
    if status != 200:
        print(f"[ERROR] Cannot find user ({status}) url={url}: {users}", file=sys.stderr)
        return 1
    if not users:
        print(f"[ERROR] User not found for email={args.email} username={args.username} url={url}", file=sys.stderr)
        return 1

    # Prefer exact email match, then exact username.
    target = None
    for user in users:
        if args.email and user.get("email", "").lower() == args.email.lower():
            target = user
            break
    if target is None:
        for user in users:
            if args.username and user.get("name") == args.username:
                target = user
                break
    if target is None:
        print(f"[ERROR] Candidates found but no exact match email={args.email} username={args.username}: {users}", file=sys.stderr)
        return 1

    print(f"[INFO] Target found: id={target.get('id')} email={target.get('email')} name={target.get('name')} active={target.get('is_active')}")
    if not args.apply:
        print("[DRY-RUN] No changes applied. Re-run with --apply.")
        return 0

    status, data, url = request_json(
        "PATCH",
        f"{base}/admin/users/{target['id']}/password",
        {"password": args.new_password},
        token=token,
    )
    if status != 200:
        print(f"[ERROR] Cannot reset password ({status}) url={url}: {data}", file=sys.stderr)
        return 1

    print(f"[OK] Password updated for user_id={target['id']}")

    # Mandatory validation: login with target credentials.
    status, login_target_data, url = request_json(
        "POST",
        f"{base}/auth/login",
        {"email": target.get("email"), "password": args.new_password},
    )
    if status != 200:
        print(f"[ERROR] Post-reset login failed ({status}) url={url}: {login_target_data}", file=sys.stderr)
        return 1

    print(f"[OK] Post-reset login validated for {target.get('email')}")
    return 0


def run_db_mode(args: argparse.Namespace) -> int:
    try:
        from pymongo import MongoClient
        import bcrypt
    except Exception as exc:
        print(f"[ERROR] DB mode requires pymongo+bcrypt: {exc}", file=sys.stderr)
        return 1

    client = MongoClient(args.mongo_url, serverSelectionTimeoutMS=10000)
    db = client[args.db_name]

    query = {"$or": [{"email": args.email}, {"name": args.username}]}
    target = db.users.find_one(query, {"_id": 0})
    if not target:
        print(f"[ERROR] Target user not found in DB: email={args.email} username={args.username}", file=sys.stderr)
        return 1

    print(f"[INFO] Target found via DB: id={target.get('id')} email={target.get('email')} name={target.get('name')}")
    if not args.apply:
        print("[DRY-RUN] No changes applied. Re-run with --apply.")
        return 0

    password_hash = bcrypt.hashpw(args.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    result = db.users.update_one(
        {"id": target["id"]},
        {"$set": {"password_hash": password_hash, "is_active": True, "role": "admin"}},
    )
    if result.matched_count != 1:
        print(f"[ERROR] Could not update DB user id={target.get('id')}", file=sys.stderr)
        return 1

    print(f"[OK] Password updated in DB for {target.get('email')} ({target.get('id')})")
    return 0


def main() -> int:
    args = parse_args()

    if args.mode == "api":
        return run_api_mode(args)
    if args.mode == "db":
        return run_db_mode(args)

    rc = run_api_mode(args)
    if rc == 0:
        return 0
    print("[WARN] API mode failed; trying DB mode...", file=sys.stderr)
    return run_db_mode(args)


if __name__ == "__main__":
    sys.exit(main())
