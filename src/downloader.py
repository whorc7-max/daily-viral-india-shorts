import hashlib
import os
import tempfile
import time
from pathlib import Path

import requests


PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PEXELS_API_KEYS = list(dict.fromkeys(
    key.strip()
    for key in os.environ.get("PEXELS_API_KEYS", "").split(",")
    if key.strip()
))
if PEXELS_API_KEY and PEXELS_API_KEY not in PEXELS_API_KEYS:
    PEXELS_API_KEYS.append(PEXELS_API_KEY)
PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
OPENVERSE_IMAGE_URL = "https://api.openverse.org/v1/images/"

MAX_CLIPS = 10
MAX_IMAGES = 24
MAX_PER_KEYWORD = 5


class VideoDownloader:
    def __init__(self):
        self.pexels_keys = PEXELS_API_KEYS
        self.next_pexels_key = 0
        if self.pexels_keys:
            print(f"Using Pexels with {len(self.pexels_keys)} key(s) plus free fallback image sources")
        else:
            print("PEXELS_API_KEY not set; using free Openverse visuals")

    def _pexels_get(self, url: str, params: dict) -> requests.Response | None:
        for offset in range(len(self.pexels_keys)):
            index = (self.next_pexels_key + offset) % len(self.pexels_keys)
            try:
                response = requests.get(
                    url,
                    headers={"Authorization": self.pexels_keys[index]},
                    params=params,
                    timeout=15,
                )
                response.raise_for_status()
                self.next_pexels_key = (index + 1) % len(self.pexels_keys)
                return response
            except Exception as exc:
                print(
                    f"  Pexels key {index + 1}/{len(self.pexels_keys)} failed "
                    f"({type(exc).__name__})"
                )
        return None

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
        if not self.pexels_keys:
            return []
        clips = []
        seen = set()
        for scene in self._queries(scenes):
            try:
                params = {"query": scene["query"], "per_page": MAX_PER_KEYWORD, "orientation": "portrait"}
                resp = self._pexels_get(PEXELS_VIDEO_URL, params)
                if resp is None:
                    continue
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
            except Exception as exc:
                print(f"  Pexels video search failed for '{scene['query']}': {exc}")
        return clips[:MAX_CLIPS]

    def search_pexels_images(self, scenes: list[dict] | list[str]) -> list[dict]:
        if not PEXELS_API_KEY:
            return []
        images = []
        seen = set()
        for scene in self._queries(scenes)[:MAX_IMAGES]:
            selected = None
            try:
                params = {"query": scene["query"], "per_page": MAX_PER_KEYWORD, "orientation": "portrait"}
                resp = self._pexels_get(PEXELS_PHOTO_URL, params)
                if resp is None:
                    continue
                for photo in resp.json().get("photos", []):
                    if photo["id"] in seen:
                        continue
                    seen.add(photo["id"])
                    url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large")
                    if url:
                        selected = {"id": photo["id"], "url": url}
                        break
            except Exception as exc:
                print(f"  Pexels search failed for '{scene['query']}': {exc}")
            images.append(selected)
        return images

    def search_openverse_images(self, scenes: list[dict] | list[str]) -> list[dict]:
        images = []
        headers = {"User-Agent": "DailyViralIndia/1.0"}
        for index, scene in enumerate(self._queries(scenes)[:MAX_IMAGES]):
            selected = None
            try:
                resp = requests.get(
                    OPENVERSE_IMAGE_URL,
                    params={"q": scene["query"], "license": "cc0", "page_size": 5},
                    headers=headers,
                    timeout=20,
                )
                resp.raise_for_status()
                candidates = [
                    item for item in resp.json().get("results", [])
                    if item.get("thumbnail") or item.get("url")
                ][:5]
                if candidates:
                    selected = {
                        "id": f"openverse_{index}",
                        "candidates": [
                            url
                            for item in candidates
                            for url in (item.get("thumbnail"), item.get("url"))
                            if url
                        ],
                    }
            except Exception as exc:
                print(f"  Openverse search failed for '{scene['query']}': {exc}")
            images.append(selected)
        return images

    def download_file(self, url: str, output_dir: str, prefix: str, default_ext: str) -> str | None:
        ext = Path(url.split("?")[0]).suffix or default_ext
        if len(ext) > 5:
            ext = ".jpg"
        hash_str = hashlib.md5(url.encode()).hexdigest()[:12]
        out_path = os.path.join(output_dir, f"{prefix}_{hash_str}{ext}")
        for attempt in range(1, 4):
            try:
                resp = requests.get(
                    url,
                    stream=True,
                    headers={"User-Agent": "DailyViralIndia/1.0"},
                    timeout=(10, 30),
                )
                resp.raise_for_status()
                with open(out_path, "wb") as file:
                    for chunk in resp.iter_content(chunk_size=8192):
                        file.write(chunk)
                return out_path
            except Exception as exc:
                if os.path.exists(out_path):
                    os.remove(out_path)
                print(f"  Download attempt {attempt}/3 failed for {prefix}_{hash_str}: {exc}")
                if attempt < 3:
                    time.sleep(attempt * 2)
        return None

    def download_clip(self, clip: dict, output_dir: str) -> str | None:
        return self.download_file(clip["url"], output_dir, f"clip_{clip['id']}", ".mp4")

    def download_image(self, image: dict, output_dir: str) -> str | None:
        candidates = image.get("candidates") or [image.get("url"), image.get("fallback_url")]
        for url in dict.fromkeys(candidate for candidate in candidates if candidate):
            path = self.download_file(url, output_dir, f"img_{image['id']}", ".jpg")
            if path:
                return path
        return None

    def download_all(
        self,
        scenes: list[dict] | list[str],
        output_dir: str | None = None,
        fallback_keywords: list[str] | None = None,
    ):
        output_dir = output_dir or tempfile.mkdtemp(prefix="shorts_")
        os.makedirs(output_dir, exist_ok=True)
        normalized = self._queries(scenes)

        print("Searching for topic-matched video clips...")
        clips = self.search_clips(normalized)
        print(f"  Found {len(clips)} clips")

        print("Searching for one visual per narration scene...")
        openverse_images = self.search_openverse_images(normalized)
        pexels_images = self.search_pexels_images(normalized) if self.pexels_keys else []
        images = [
            (pexels_images[index] if index < len(pexels_images) else None)
            or (openverse_images[index] if index < len(openverse_images) else None)
            for index in range(len(normalized))
        ]
        if fallback_keywords and any(image is None for image in images):
            fallback_scenes = [{"search_query": keyword, "image_prompt": keyword} for keyword in fallback_keywords]
            fallback_images = self.search_pexels_images(fallback_scenes) if PEXELS_API_KEY else []
            for index, image in enumerate(images):
                if image is None and fallback_images:
                    images[index] = fallback_images[index % len(fallback_images)]
        print(f"  Found {sum(image is not None for image in images)} licensed images")

        image_paths = []
        for image in images:
            image_paths.append(self.download_image(image, output_dir) if image else None)

        if any(path is None for path in image_paths):
            print("  Some scenes had no matching licensed result; those scenes use a generated background")
        return [path for clip in clips if (path := self.download_clip(clip, output_dir))], image_pathsimport hashlib
import os
import tempfile
import time
from pathlib import Path

import requests


PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
OPENVERSE_IMAGE_URL = "https://api.openverse.org/v1/images/"

MAX_CLIPS = 10
MAX_IMAGES = 24
MAX_PER_KEYWORD = 5


class VideoDownloader:
    def __init__(self):
        self.pexels_headers = {"Authorization": PEXELS_API_KEY} if PEXELS_API_KEY else {}
        if PEXELS_API_KEY:
            print("Using Pexels plus free fallback image sources")
        else:
            print("PEXELS_API_KEY not set; using free Openverse visuals")

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
            try:
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
            except Exception as exc:
                print(f"  Pexels video search failed for '{scene['query']}': {exc}")
        return clips[:MAX_CLIPS]

    def search_pexels_images(self, scenes: list[dict] | list[str]) -> list[dict]:
        if not PEXELS_API_KEY:
            return []
        images = []
        seen = set()
        for scene in self._queries(scenes)[:MAX_IMAGES]:
            selected = None
            try:
                params = {"query": scene["query"], "per_page": MAX_PER_KEYWORD, "orientation": "portrait"}
                resp = requests.get(PEXELS_PHOTO_URL, headers=self.pexels_headers, params=params, timeout=15)
                resp.raise_for_status()
                for photo in resp.json().get("photos", []):
                    if photo["id"] in seen:
                        continue
                    seen.add(photo["id"])
                    url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large")
                    if url:
                        selected = {"id": photo["id"], "url": url}
                        break
            except Exception as exc:
                print(f"  Pexels search failed for '{scene['query']}': {exc}")
            images.append(selected)
        return images

    def search_openverse_images(self, scenes: list[dict] | list[str]) -> list[dict]:
        images = []
        headers = {"User-Agent": "DailyViralIndia/1.0"}
        for index, scene in enumerate(self._queries(scenes)[:MAX_IMAGES]):
            selected = None
            try:
                resp = requests.get(
                    OPENVERSE_IMAGE_URL,
                    params={"q": scene["query"], "license": "cc0", "page_size": 5},
                    headers=headers,
                    timeout=20,
                )
                resp.raise_for_status()
                candidates = [
                    item for item in resp.json().get("results", [])
                    if item.get("thumbnail") or item.get("url")
                ][:5]
                if candidates:
                    selected = {
                        "id": f"openverse_{index}",
                        "candidates": [
                            url
                            for item in candidates
                            for url in (item.get("thumbnail"), item.get("url"))
                            if url
                        ],
                    }
            except Exception as exc:
                print(f"  Openverse search failed for '{scene['query']}': {exc}")
            images.append(selected)
        return images

    def download_file(self, url: str, output_dir: str, prefix: str, default_ext: str) -> str | None:
        ext = Path(url.split("?")[0]).suffix or default_ext
        if len(ext) > 5:
            ext = ".jpg"
        hash_str = hashlib.md5(url.encode()).hexdigest()[:12]
        out_path = os.path.join(output_dir, f"{prefix}_{hash_str}{ext}")
        for attempt in range(1, 4):
            try:
                resp = requests.get(
                    url,
                    stream=True,
                    headers={"User-Agent": "DailyViralIndia/1.0"},
                    timeout=(10, 30),
                )
                resp.raise_for_status()
                with open(out_path, "wb") as file:
                    for chunk in resp.iter_content(chunk_size=8192):
                        file.write(chunk)
                return out_path
            except Exception as exc:
                if os.path.exists(out_path):
                    os.remove(out_path)
                print(f"  Download attempt {attempt}/3 failed for {prefix}_{hash_str}: {exc}")
                if attempt < 3:
                    time.sleep(attempt * 2)
        return None

    def download_clip(self, clip: dict, output_dir: str) -> str | None:
        return self.download_file(clip["url"], output_dir, f"clip_{clip['id']}", ".mp4")

    def download_image(self, image: dict, output_dir: str) -> str | None:
        candidates = image.get("candidates") or [image.get("url"), image.get("fallback_url")]
        for url in dict.fromkeys(candidate for candidate in candidates if candidate):
            path = self.download_file(url, output_dir, f"img_{image['id']}", ".jpg")
            if path:
                return path
        return None

    def download_all(
        self,
        scenes: list[dict] | list[str],
        output_dir: str | None = None,
        fallback_keywords: list[str] | None = None,
    ):
        output_dir = output_dir or tempfile.mkdtemp(prefix="shorts_")
        os.makedirs(output_dir, exist_ok=True)
        normalized = self._queries(scenes)

        print("Searching for topic-matched video clips...")
        clips = self.search_clips(normalized)
        print(f"  Found {len(clips)} clips")

        print("Searching for one visual per narration scene...")
        openverse_images = self.search_openverse_images(normalized)
        pexels_images = self.search_pexels_images(normalized) if PEXELS_API_KEY else []
        images = [
            (pexels_images[index] if index < len(pexels_images) else None)
            or (openverse_images[index] if index < len(openverse_images) else None)
            for index in range(len(normalized))
        ]
        if fallback_keywords and any(image is None for image in images):
            fallback_scenes = [{"search_query": keyword, "image_prompt": keyword} for keyword in fallback_keywords]
            fallback_images = self.search_pexels_images(fallback_scenes) if PEXELS_API_KEY else []
            for index, image in enumerate(images):
                if image is None and fallback_images:
                    images[index] = fallback_images[index % len(fallback_images)]
        print(f"  Found {sum(image is not None for image in images)} licensed images")

        image_paths = []
        for image in images:
            image_paths.append(self.download_image(image, output_dir) if image else None)

        if any(path is None for path in image_paths):
            print("  Some scenes had no matching licensed result; those scenes use a generated background")
        return [path for clip in clips if (path := self.download_clip(clip, output_dir))], image_paths
