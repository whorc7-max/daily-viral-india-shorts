import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


def main():
    missing = [
        name
        for name in ("YT_REFRESH_TOKEN", "YT_CLIENT_ID", "YT_CLIENT_SECRET")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(
            "Missing YouTube secret(s): " + ", ".join(missing) + ". "
            "Reauthorize the YouTube channel and update GitHub Secrets."
        )

    credentials = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
    )
    try:
        credentials.refresh(Request())
    except Exception as exc:
        raise RuntimeError(
            "YouTube authorization is no longer valid. Reauthorize the channel "
            "once and replace YT_REFRESH_TOKEN in GitHub Secrets."
        ) from exc

    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY is not set; the script generator will use its safe fallback.")
    print("Credential health check passed; secret values were not printed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Health check failed: {exc}", file=sys.stderr)
        sys.exit(1)
