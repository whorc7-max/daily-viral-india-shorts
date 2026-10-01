import os
import time
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")


class YouTubeUploader:
    def __init__(self):
        missing = []
        if not YT_REFRESH_TOKEN:
            missing.append("YT_REFRESH_TOKEN")
        if not YT_CLIENT_ID:
            missing.append("YT_CLIENT_ID")
        if not YT_CLIENT_SECRET:
            missing.append("YT_CLIENT_SECRET")
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Run auth_setup.py locally to obtain these."
            )

    def _get_access_token(self) -> str:
        creds = Credentials(
            None,
            refresh_token=YT_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=YT_CLIENT_ID,
            client_secret=YT_CLIENT_SECRET,
        )
        for attempt in range(1, 4):
            try:
                creds.refresh(Request())
                return creds.token
            except Exception as exc:
                if attempt == 3:
                    raise RuntimeError(
                        "YouTube authorization failed. Reauthorize the channel and "
                        "replace YT_REFRESH_TOKEN in GitHub Secrets."
                    ) from exc
                print(f"YouTube token refresh attempt {attempt}/3 failed; retrying")
                time.sleep(attempt * 2)

    def upload(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        visibility: str = "public",
    ):
        access_token = self._get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
            },
            "status": {
                "privacyStatus": visibility,
                "selfDeclaredMadeForKids": False,
            },
        }

        print("Initiating upload...")
        init_url = (
            "https://www.googleapis.com/upload/youtube/v3/videos"
            "?part=snippet,status&uploadType=resumable"
        )
        retryable_statuses = {429, 500, 502, 503, 504}
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(init_url, headers=headers, json=body, timeout=30)
            except requests.RequestException as exc:
                if attempt == max_attempts:
                    raise RuntimeError(
                        f"YouTube upload initialization failed after {max_attempts} attempts due to a network error."
                    ) from exc
                delay = min(2 ** attempt, 30)
                print(f"Upload initialization network error; retrying in {delay}s ({attempt}/{max_attempts})")
                time.sleep(delay)
                continue

            if resp.ok:
                break
            if resp.status_code not in retryable_statuses or attempt == max_attempts:
                raise RuntimeError(
                    f"YouTube upload initialization failed (HTTP {resp.status_code}) after {attempt} attempts."
                )

            try:
                retry_after = float(resp.headers.get("Retry-After", ""))
            except (TypeError, ValueError):
                retry_after = 0
            delay = min(max(retry_after, 2 ** attempt), 30)
            print(f"Upload initialization failed (HTTP {resp.status_code}); retrying in {delay}s ({attempt}/{max_attempts})")
            time.sleep(delay)

        upload_url = resp.headers.get("Location")
        if not upload_url:
            raise RuntimeError("YouTube did not return a resumable upload URL.")

        print("Uploading video file...")
        file_size = os.path.getsize(video_path)
        with open(video_path, "rb") as f:
            resp = requests.put(
                upload_url,
                data=f,
                headers={
                    "Content-Length": str(file_size),
                    "Content-Type": "video/*",
                },
                timeout=600,
            )
        resp.raise_for_status()
        video_id = resp.json().get("id")
        print(f"  Uploaded! Video ID: {video_id}")
        print(f"  https://youtu.be/{video_id}")
