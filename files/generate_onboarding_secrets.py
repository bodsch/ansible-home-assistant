#!/usr/bin/env python3
"""Generate the .storage files needed to seed Home Assistant onboarding.

Run this with the Home Assistant virtualenv interpreter so that ``bcrypt`` and
``PyJWT`` (both core Home Assistant dependencies) are importable. All inputs are
passed via environment variables - the plaintext password in particular is kept
out of the process argument list. The result is a single JSON object printed to
stdout:

    {"files": {"auth": {...}, "auth_provider.homeassistant": {...},
               "onboarding": {...}, "person": {...}},
     "access_token": "<bearer token or null>"}

Building the documents here (instead of in Jinja) keeps the JSON types correct
- ints stay ints, booleans stay booleans - which Home Assistant's store loader
is picky about.
"""

import base64
import datetime
import json
import os
import secrets
import uuid

import bcrypt


def _schema(schema, key, field, default):
    """Return an int schema version, falling back to a sane default."""
    return int(schema.get(key, {}).get(field, default))


def main():
    password = os.environ["HA_PASSWORD"].encode()
    username = os.environ["HA_USERNAME"]
    name = os.environ.get("HA_NAME") or "Admin"
    make_token = os.environ.get("HA_MAKE_TOKEN") == "1"
    make_person = os.environ.get("HA_PERSON") == "1"
    token_name = os.environ.get("HA_TOKEN_NAME") or "ansible"
    ha_version = os.environ.get("HA_VERSION") or None
    schema = json.loads(os.environ.get("HA_SCHEMA") or "{}")

    user_id = uuid.uuid4().hex
    credential_id = uuid.uuid4().hex
    person_id = uuid.uuid4().hex

    # Home Assistant stores the password as base64(bcrypt(password)).
    password_hash = base64.b64encode(
        bcrypt.hashpw(password, bcrypt.gensalt(rounds=12))
    ).decode()

    refresh_tokens = []
    access_token = None
    if make_token:
        import jwt  # PyJWT - core Home Assistant dependency

        now = datetime.datetime.now(datetime.timezone.utc)
        expiration = datetime.timedelta(days=3650)
        refresh_token_id = uuid.uuid4().hex
        jwt_key = secrets.token_hex(64)

        refresh_tokens.append(
            {
                "id": refresh_token_id,
                "user_id": user_id,
                "client_id": None,
                "client_name": token_name,
                "client_icon": None,
                "token_type": "long_lived_access_token",
                "created_at": now.isoformat(),
                "access_token_expiration": expiration.total_seconds(),
                "token": secrets.token_hex(64),
                "jwt_key": jwt_key,
                "last_used_at": None,
                "last_used_ip": None,
                "expire_at": None,
                "credential_id": None,
                "version": ha_version,
            }
        )
        # The bearer token is a JWT signed with the refresh token's jwt_key,
        # exactly as Home Assistant's auth.async_create_access_token() builds it.
        access_token = jwt.encode(
            {"iss": refresh_token_id, "iat": now, "exp": now + expiration},
            jwt_key,
            algorithm="HS256",
        )

    auth = {
        "version": _schema(schema, "auth", "version", 1),
        "minor_version": _schema(schema, "auth", "minor_version", 1),
        "key": "auth",
        "data": {
            "users": [
                {
                    "id": user_id,
                    "group_ids": ["system-admin"],
                    "is_owner": True,
                    "is_active": True,
                    "name": name,
                    "system_generated": False,
                    "local_only": False,
                }
            ],
            "groups": [
                {"id": "system-admin", "name": "Administrators"},
                {"id": "system-users", "name": "Users"},
                {"id": "system-read-only", "name": "Read Only"},
            ],
            "credentials": [
                {
                    "id": credential_id,
                    "user_id": user_id,
                    "auth_provider_type": "homeassistant",
                    "auth_provider_id": None,
                    "data": {"username": username},
                }
            ],
            "refresh_tokens": refresh_tokens,
        },
    }

    auth_provider = {
        "version": _schema(schema, "auth_provider", "version", 1),
        "minor_version": _schema(schema, "auth_provider", "minor_version", 1),
        "key": "auth_provider.homeassistant",
        "data": {"users": [{"username": username, "password": password_hash}]},
    }

    onboarding = {
        "version": _schema(schema, "onboarding", "version", 4),
        "minor_version": _schema(schema, "onboarding", "minor_version", 1),
        "key": "onboarding",
        "data": {"done": ["user", "core_config", "analytics", "integration"]},
    }

    files = {
        "auth": auth,
        "auth_provider.homeassistant": auth_provider,
        "onboarding": onboarding,
    }

    if make_person:
        files["person"] = {
            "version": _schema(schema, "person", "version", 1),
            "minor_version": _schema(schema, "person", "minor_version", 2),
            "key": "person",
            "data": {
                "items": [
                    {
                        "id": person_id,
                        "name": name,
                        "user_id": user_id,
                        "device_trackers": [],
                        "picture": None,
                    }
                ]
            },
        }

    print(json.dumps({"files": files, "access_token": access_token}))


if __name__ == "__main__":
    main()
