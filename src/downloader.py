import hashlib
import os
import tempfile
from pathlib import Path
from urllib.parse import quote

import requests


PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
OPENVERSE_IMAGE_URL = "https://api.openverse.org/v1/images/"
POLLINATIONS_IMAGE_URL = "https://image.pollinations.ai/prompt/"

MAX_CLIPS = 10
MAX_IMAGES = 8
MAX_PER_KEYWORD = 5


class VideoDownloader:
    def __init__(self):
        self.pexels_headers = {"Authorization": PEXELS_API_KEY} if PEXELS_API_KEY else {}
        if PEXELS_API_KEY:
            print("Using Pexels plus free fallback image sources")
        else:
            print("PEXELS_API_KEY not set; using free Openverse/Pollinations visuals")

    def _queries(self, scenes: list[dict] | list[str]) -> list[dict]:
        normalized = []
        for scene in scenes:
            if isinstance(scene, dict):
                query = str(scene.get("search_query", "")).strip()
                prompt = str(scene.get("image_prompt", "")).strip()
            else:
                query = str(scene).strip()
                prompt = query
            if query:
                normalized.append({"query": query, "prompt": prompt or query})
        return normalized

    def search_clips(self, scenes: list[dict] | list[str]) -> list[dict]:
        if not PEXELS_API_KEY:
            return []
        clips = []
        seen = set()
        for scene in self._queries(scenes):
            params = {"query": scene["query"], "per_page": MAX_PER_KEYWORD, "orientation": "portrait"}
            resp = requests.get(PEXELS_VIDEO_URL, headers=self.pexels_headers, params=params, timeout=15)
            resp.raise_for_status()
            for video in resp.json().get("videos", []):
                if video["id"] in seen:
                    continue
                seen.add(video["id"])
                for file in video.get("video_files", []):
                    if file.get("quality") in ("sd", "hd") and file.get("link"):
                        clips.append({"id": video["id"], "url": file["link"]})
                        break
                if len(clips) >= MAX_CLIPS:
                    return clips[:MAX_CLIPS]
        return clips[:MAX_CLIPS]

    def search_pexels_images(self, scenes: list[dict] | list[str]) -> list[dict]:
        if not PEXELS_API_KEY:
            return []
        images = []
        seen = set()
        for scene in self._queries(scenes):
            params = {"query": scene["query"], "per_page": MAX_PER_KEYWORD, "orientation": "portrait"}
            resp = requests.get(PEXELS_PHOTO_URL, headers=self.pexels_headers, params=params, timeout=15)
            resp.raise_for_status()
            for photo in resp.json().get("photos", []):
                if photo["id"] in seen:
                    continue
                seen.add(photo["id"])
                url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large")
                if url:
                    images.append({"id": photo["id"], "url": url})
                if len(images) >= MAX_IMAGES:
                    return images[:MAX_IMAGES]
        return images[:MAX_IMAGES]

    def search_openverse_images(self, scenes: list[dict] | list[str]) -> list[dict]:
        images = []
        headers = {"User-Agent": "DailyViralIndia/1.0"}
        for scene in self._queries(scenes):
            try:
                resp = requests.get(
                    OPENVERSE_IMAGE_URL,
                    params={"q": scene["query"], "license": "cc0", "page_size": 5},
                    headers=headers,
                    timeout=20,
                )
                resp.raise_for_status()
                result = next((item for item in resp.json().get("results", []) if item.get("url")), None)
                if result:
                    images.append({"id": f"openverse_{len(images)}", "url": result["url"]})
            except Exception as exc:
                print(f"  Openverse search failed for '{scene['query']}': {exc}")
            if len(images) >= MAX_IMAGES:
                break
        return images[:MAX_IMAGES]

    def _ai_image(self, scene: dict, output_dir: str, index: int) -> str | None:
        prompt = (
            f"{scene['prompt']}, vertical 9:16 editorial news illustration, realistic, "
            "no text, no logos, no watermark"
        )
        url = POLLINATIONS_IMAGE_URL + quote(prompt)
        try:
            response = requests.get(
                url,
                params={"width": 1080, "height": 1920, "nologo": "true"},
                headers={"User-Agent": "DailyViralIndia/1.0"},
                timeout=90,
            )
            response.raise_for_status()
            path = os.path.join(output_dir, f"scene_{index:02d}_ai.jpg")
            with open(path, "wb") as file:
                file.write(response.content)
            return path
        except Exception as exc:
            print(f"  AI visual failed for scene {index + 1}: {exc}")
            return None

    def download_file(self, url: str, output_dir: str, prefix: str, default_ext: str) -> str | None:
        ext = Path(url.split("?")[0]).suffix or default_ext
        if len(ext) > 5:
            ext = ".jpg"
        hash_str = hashlib.md5(url.encode()).hexdigest()[:12]
        out_path = os.path.join(output_dir, f"{prefix}_{hash_str}{ext}")
        try:
            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            with open(out_path, "wb") as file:
                for chunk in resp.iter_content(chunk_size=8192):
                    file.write(chunk)
            return out_path
        except Exception as exc:
            print(f"  Failed to download {prefix}_{hash_str}: {exc}")
            return None

    def download_clip(self, clip: dict, output_dir: str) -> str | None:
        return self.download_file(clip["url"], output_dir, f"clip_{clip['id']}", ".mp4")

    def download_image(self, image: dict, output_dir: str) -> str | None:
        return self.download_file(image["url"], output_dir, f"img_{image['id']}", ".jpg")

    def download_all(self, scenes: list[dict] | list[str], output_dir: str | None = None):
        output_dir = output_dir or tempfile.mkdtemp(prefix="shorts_")
        os.makedirs(output_dir, exist_ok=True)
        normalized = self._queries(scenes)

        print("Searching for topic-matched video clips...")
        clips = self.search_clips(normalized)
        print(f"  Found {len(clips)} clips")

        print("Searching for one visual per narration scene...")
        images = self.search_pexels_images(normalized) if PEXELS_API_KEY else []
        if not images:
            images = self.search_openverse_images(normalized)
        print(f"  Found {len(images)} licensed images")

        image_paths = []
        for index, image in enumerate(images):
            path = self.download_image(image, output_dir)
            if path:
                image_paths.append(path)

        while len(image_paths) < len(normalized):
            index = len(image_paths)
            path = self._ai_image(normalized[index], output_dir, index)
            if not path:
                break
            image_paths.append(path)
        return [path for clip in clips if (path := self.download_clip(clip, output_dir))], image_paths
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
