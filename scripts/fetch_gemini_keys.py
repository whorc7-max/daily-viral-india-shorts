import os
import sys
from urllib.parse import quote

import requests


FIREBASE_API_KEY = os.environ.get(
    "FIREBASE_API_KEY",
    "AIzaSyDZxgX4SBNfWTMMNjaCPGpwM-fJnzz-qQY",
)
FIREBASE_PROJECT_ID = "radiant-song-lmn89"
FIREBASE_DATABASE_ID = os.environ.get(
    "FIREBASE_DATABASE_ID",
    "ai-studio-f73e5bc0-cd96-44a3-ac5c-632b8094364a",
)
FIREBASE_COLLECTION = os.environ.get("FIREBASE_COLLECTION", "apiKeys")
KEY_OUTPUT_PREFIX = os.environ.get("KEY_OUTPUT_PREFIX", "GEMINI")
TOKEN_URL = "https://securetoken.googleapis.com/v1/token"


def _refresh_id_token(refresh_token: str) -> tuple[str, str]:
    response = requests.post(
        TOKEN_URL,
        params={"key": FIREBASE_API_KEY},
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["id_token"], payload["user_id"]


def _read_firestore_keys(id_token: str, user_id: str) -> list[str]:
    path = "/v1/projects/{}/databases/{}/documents/users/{}/{}".format(
        FIREBASE_PROJECT_ID,
        FIREBASE_DATABASE_ID,
        quote(user_id, safe=""),
        FIREBASE_COLLECTION,
    )
    keys: list[str] = []
    page_token = None

    while True:
        params = {"pageSize": 100, "key": FIREBASE_API_KEY}
        if page_token:
            params["pageToken"] = page_token
        response = requests.get(
            "https://firestore.googleapis.com" + path,
            params=params,
            headers={"Authorization": f"Bearer {id_token}"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        for document in payload.get("documents", []):
            value = document.get("fields", {}).get("key", {}).get("stringValue")
            if value and value.strip() and value.strip() not in keys:
                keys.append(value.strip())
        page_token = payload.get("nextPageToken")
        if not page_token:
            return keys


def _configured_keys() -> list[str]:
    refresh_token = os.environ.get("FIREBASE_REFRESH_TOKEN", "").strip()
    fallback = os.environ.get(f"{KEY_OUTPUT_PREFIX}_API_KEY", "").strip()
    # Accept comma- or newline-separated keys for deterministic rotation.
    fallback_keys = [
        value.strip()
        for value in fallback.replace("\n", ",").split(",")
        if value.strip()
    ]
    keys: list[str] = []

    if refresh_token:
        try:
            id_token, user_id = _refresh_id_token(refresh_token)
            keys.extend(_read_firestore_keys(id_token, user_id))
            print(
                f"Loaded {len(keys)} {KEY_OUTPUT_PREFIX} key(s) from the Firebase vault.",
                file=sys.stderr,
            )
        except Exception:
            if fallback_keys:
                print(
                    f"Using {len(fallback_keys)} configured static {KEY_OUTPUT_PREFIX} key(s); Firebase vault sync skipped.",
                    file=sys.stderr,
                )
            else:
                print(
                    f"Firebase vault unavailable and no static {KEY_OUTPUT_PREFIX} key is configured.",
                    file=sys.stderr,
                )
    elif not fallback_keys:
        print(
            f"FIREBASE_REFRESH_TOKEN is not set and no static {KEY_OUTPUT_PREFIX} key is configured.",
            file=sys.stderr,
        )

    for fallback_key in fallback_keys:
        if fallback_key not in keys:
            keys.append(fallback_key)
    return keys


def main() -> None:
    keys = _configured_keys()
    if not keys:
        return
    # This output is redirected to GitHub's environment file by the workflow.
    print(f"{KEY_OUTPUT_PREFIX}_API_KEY={keys[0]}")
    print(f"{KEY_OUTPUT_PREFIX}_API_KEYS={','.join(keys)}")


if __name__ == "__main__":
    main()

