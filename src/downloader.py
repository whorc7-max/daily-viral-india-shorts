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

MAX_IMAGES = 24
MAX_PER_KEYWORD = 5


class VideoDownloader:
    def __init__(self):
        self.pexels_keys = PEXELS_API_KEYS
        self.next_pexels_key = 0
        if self.pexels_keys:
            print(f"Using Pexels video-first with {len(self.pexels_keys)} key(s) plus image fallback sources")
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

    def search_clips(self, scenes: list[dict] | list[str]) -> list[dict | None]:
        if not self.pexels_keys:
            return []
        normalized = self._queries(scenes)
        clips = [None] * len(normalized)
        seen = set()

        def find_video(query: str) -> dict | None:
            try:
                responses = [
                    {"query": query, "per_page": MAX_PER_KEYWORD, "orientation": "portrait"},
                    {"query": query, "per_page": MAX_PER_KEYWORD},
                ]
                for params in responses:
                    resp = self._pexels_get(PEXELS_VIDEO_URL, params)
                    if resp is None:
                        continue
                    for video in resp.json().get("videos", []):
                        if video["id"] in seen:
                            continue
                        files = [
                            file for file in video.get("video_files", [])
                            if file.get("link") and file.get("width") and file.get("height")
                        ]
                        if not files:
                            continue
                        portrait_files = [file for file in files if file["height"] >= file["width"]]
                        selected_file = (portrait_files or files)[0]
                        seen.add(video["id"])
                        return {"id": video["id"], "url": selected_file["link"]}
            except Exception as exc:
                print(f"  Pexels video search failed for '{query}': {exc}")
            return None

        for index, scene in enumerate(normalized):
            clips[index] = find_video(scene["query"])

        remaining = [index for index, clip in enumerate(clips) if clip is None]
        generic_queries = ["India", "news", "people", "technology", "business", "nature"]
        for query in generic_queries:
            if not remaining:
                break
            selected = find_video(query)
            if selected:
                clips[remaining.pop(0)] = selected
        return clips

    def search_pexels_images(self, scenes: list[dict] | list[str]) -> list[dict]:
        if not self.pexels_keys:
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

        print("Searching for topic-matched Pexels video clips first...")
        clips = self.search_clips(normalized)
        print(f"  Found {sum(clip is not None for clip in clips)} clips")

        clips = clips + [None] * (len(normalized) - len(clips))
        image_indexes = [index for index, clip in enumerate(clips) if clip is None]
        image_scenes = [normalized[index] for index in image_indexes]
        print(f"Searching for image fallback for {len(image_scenes)} scene(s)...")
        openverse_images = self.search_openverse_images(image_scenes)
        pexels_images = self.search_pexels_images(image_scenes) if self.pexels_keys else []
        images = [None] * len(normalized)
        for image_index, scene_index in enumerate(image_indexes):
            images[scene_index] = (
                pexels_images[image_index] if image_index < len(pexels_images) else None
            ) or (
                openverse_images[image_index] if image_index < len(openverse_images) else None
            )
        if fallback_keywords and any(image is None for image in images):
            fallback_scenes = [{"search_query": keyword, "image_prompt": keyword} for keyword in fallback_keywords]
            fallback_images = self.search_pexels_images(fallback_scenes) if self.pexels_keys else []
            for index, image in enumerate(images):
                if image is None and fallback_images:
                    images[index] = fallback_images[index % len(fallback_images)]
        print(f"  Found {sum(image is not None for image in images)} image fallbacks")

        clip_paths = [
            self.download_clip(clip, output_dir) if clip else None
            for clip in clips
        ]
        image_paths = []
        for image in images:
            image_paths.append(self.download_image(image, output_dir) if image else None)

        missing = sum(
            clip_path is None and image_path is None
            for clip_path, image_path in zip(clip_paths, image_paths)
        )
        if missing:
            print(f"  {missing} scene(s) had no matching licensed result; using generated backgrounds")
        return clip_paths, image_paths
