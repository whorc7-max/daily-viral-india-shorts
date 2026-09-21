import os
import requests
import tempfile
from pathlib import Path
import hashlib

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
HEADERS = {"Authorization": PEXELS_API_KEY}

MAX_CLIPS = 10
MAX_IMAGES = 8
MAX_PER_KEYWORD = 5


class VideoDownloader:
    def __init__(self):
        if not PEXELS_API_KEY:
            print("PEXELS_API_KEY not set; using generated gradient backgrounds")

    def search_clips(self, keywords: list[str]) -> list[dict]:
        if not PEXELS_API_KEY:
            return []
        seen = set()
        clips = []
        for kw in keywords:
            params = {"query": kw, "per_page": MAX_PER_KEYWORD, "orientation": "portrait"}
            resp = requests.get(PEXELS_VIDEO_URL, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for video in data.get("videos", []):
                vid_id = video["id"]
                if vid_id in seen:
                    continue
                seen.add(vid_id)
                for file in video.get("video_files", []):
                    if file["quality"] in ("sd", "hd") and file.get("link"):
                        clips.append({
                            "id": vid_id,
                            "url": file["link"],
                            "width": file.get("width", 0),
                            "height": file.get("height", 0),
                            "duration": video.get("duration", 10),
                        })
                        break
                if len(clips) >= MAX_CLIPS:
                    break
            if len(clips) >= MAX_CLIPS:
                break
        return clips[:MAX_CLIPS]

    def search_images(self, keywords: list[str]) -> list[dict]:
        if not PEXELS_API_KEY:
            return []
        seen = set()
        images = []
        for kw in keywords:
            params = {"query": kw, "per_page": MAX_PER_KEYWORD, "orientation": "portrait"}
            resp = requests.get(PEXELS_PHOTO_URL, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for photo in data.get("photos", []):
                pid = photo["id"]
                if pid in seen:
                    continue
                seen.add(pid)
                images.append({
                    "id": pid,
                    "url": photo["src"]["large"],
                })
                if len(images) >= MAX_IMAGES:
                    break
            if len(images) >= MAX_IMAGES:
                break
        return images[:MAX_IMAGES]

    def download_file(self, url: str, output_dir: str, prefix: str) -> str | None:
        ext = Path(url.split("?")[0]).suffix or ".mp4"
        hash_str = hashlib.md5(url.encode()).hexdigest()[:12]
        out_path = os.path.join(output_dir, f"{prefix}_{hash_str}{ext}")
        try:
            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return out_path
        except Exception as e:
            print(f"  Failed to download {prefix}_{hash_str}: {e}")
            return None

    def download_clip(self, clip: dict, output_dir: str) -> str | None:
        return self.download_file(clip["url"], output_dir, f"clip_{clip['id']}")

    def download_image(self, image: dict, output_dir: str) -> str | None:
        return self.download_file(image["url"], output_dir, f"img_{image['id']}")

    def download_all(self, keywords: list[str], output_dir: str | None = None):
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="shorts_")
        else:
            os.makedirs(output_dir, exist_ok=True)

        print("Searching Pexels for video clips...")
        clips = self.search_clips(keywords)
        print(f"  Found {len(clips)} clips")

        print("Searching Pexels for images...")
        images = self.search_images(keywords)
        print(f"  Found {len(images)} images")

        video_paths = []
        for clip in clips:
            path = self.download_clip(clip, output_dir)
            if path:
                video_paths.append(path)

        image_paths = []
        for img in images:
            path = self.download_image(img, output_dir)
            if path:
                image_paths.append(path)

        return video_paths, image_paths
