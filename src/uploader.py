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
        resp = requests.post(init_url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        upload_url = resp.headers["Location"]

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
