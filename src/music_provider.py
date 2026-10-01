import hashlib
import json
import os
from urllib.parse import urlsplit

import requests


OPENVERSE_AUDIO_URL = "https://api.openverse.org/v1/audio/"
CC0_LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
MAX_MUSIC_BYTES = 40 * 1024 * 1024


class MusicProvider:
    @staticmethod
    def _queries(topic: str, keywords: list[str]) -> list[str]:
        text = " ".join([topic, *(str(word) for word in keywords)]).lower()
        profiles = [
            (("rain", "rainfall", "monsoon", "baarish", "barish", "barsa", "water"), [
                "romantic monsoon instrumental",
                "upbeat romantic rain instrumental",
                "gentle Indian instrumental music",
            ]),
            (("cricket", "football", "sports", "stadium", "match"), [
                "energetic sports instrumental",
                "uplifting drums instrumental music",
            ]),
            (("comedy", "funny", "meme", "joke", "humor"), [
                "playful upbeat instrumental",
                "quirky comedy instrumental music",
            ]),
            (("love", "romance", "emotional", "heartbreak", "relationship"), [
                "romantic piano instrumental",
                "emotional acoustic instrumental music",
            ]),
            (("technology", "science", "robot", "space", "artificial intelligence", " ai "), [
                "modern electronic instrumental",
                "uplifting technology background music",
            ]),
            (("news", "crime", "accident", "disaster", "surprising"), [
                "cinematic dramatic instrumental",
                "suspenseful documentary instrumental music",
            ]),
            (("nature", "forest", "wildlife", "animal", "bird"), [
                "calm acoustic nature instrumental",
                "peaceful piano instrumental music",
            ]),
        ]
        for terms, queries in profiles:
            if any(term in text for term in terms):
                return queries + ["uplifting cinematic instrumental"]

        base = " ".join(str(word).strip() for word in keywords[:2] if str(word).strip())
        queries = [f"{base} instrumental music"] if base else []
        return queries + [
            "uplifting cinematic instrumental",
            "melodic background instrumental music",
        ]

    @staticmethod
    def _authorized_tracks(topic: str, keywords: list[str]) -> list[tuple[int, dict]]:
        raw_catalog = os.environ.get("LICENSED_MUSIC_CATALOG_JSON", "").strip()
        if not raw_catalog:
            return []
        try:
            tracks = json.loads(raw_catalog).get("tracks", [])
        except (AttributeError, json.JSONDecodeError):
            print("  Licensed music catalog is invalid; skipping it")
            return []
        if not isinstance(tracks, list):
            print("  Licensed music catalog is invalid; skipping it")
            return []

        text = " ".join([topic, *(str(word) for word in keywords)]).lower()
        matches = []
        for track in tracks:
            if not isinstance(track, dict) or track.get("authorized_for_youtube") is not True:
                continue
            if not isinstance(track.get("rights_holder"), str) or not track["rights_holder"].strip():
                continue
            if not isinstance(track.get("direct_url"), str):
                continue
            direct_url = track["direct_url"].strip()
            parsed = urlsplit(direct_url)
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or not host or "y2mate" in host:
                continue

            tags = track.get("tags", [])
            if not isinstance(tags, list):
                continue
            matching_tags = [
                str(tag).strip().lower()
                for tag in tags
                if str(tag).strip() and str(tag).strip().lower() in text
            ]
            if matching_tags:
                matches.append((len(matching_tags), track))
        return sorted(matches, key=lambda item: item[0], reverse=True)

    def _download_authorized_track(
        self,
        topic: str,
        keywords: list[str],
        output_dir: str,
    ) -> str | None:
        headers = {"User-Agent": "DailyViralIndia/1.0"}
        for _score, track in self._authorized_tracks(topic, keywords):
            direct_url = track["direct_url"].strip()
            host = (urlsplit(direct_url).hostname or "").lower()
            output_path = os.path.join(
                output_dir,
                f"licensed_music_{hashlib.sha256(direct_url.encode()).hexdigest()[:12]}.audio",
            )
            try:
                response = requests.get(
                    direct_url,
                    headers=headers,
                    stream=True,
                    allow_redirects=False,
                    timeout=(5, 45),
                )
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()
                if response.status_code >= 300 or "text/html" in content_type:
                    continue

                downloaded = 0
                with open(output_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        downloaded += len(chunk)
                        if downloaded > MAX_MUSIC_BYTES:
                            raise ValueError("Licensed music file exceeded 40 MB")
                        file.write(chunk)
                if not downloaded:
                    os.remove(output_path)
                    continue

                with open(
                    os.path.join(output_dir, "music_source.json"),
                    "w",
                    encoding="utf-8",
                ) as file:
                    json.dump(
                        {
                            "title": track.get("title") or "Licensed track",
                            "rights_holder": track["rights_holder"],
                            "license": "User-confirmed YouTube permission",
                            "source_host": host,
                            "matched_tags": track.get("tags", []),
                        },
                        file,
                        ensure_ascii=False,
                        indent=2,
                    )
                print("  Selected a topic-matched, user-authorized track")
                return output_path
            except Exception as exc:
                try:
                    os.remove(output_path)
                except OSError:
                    pass
                print(f"  Authorized track download failed: {type(exc).__name__}")
        return None

    def download(
        self,
        keywords: list[str],
        output_dir: str,
        topic: str = "",
    ) -> str | None:
        os.makedirs(output_dir, exist_ok=True)
        licensed_track = self._download_authorized_track(
            topic, keywords or [], output_dir
        )
        if licensed_track:
            return licensed_track

        queries = self._queries(topic, keywords or [])
        headers = {"User-Agent": "DailyViralIndia/1.0"}

        for query in queries:
            try:
                response = requests.get(
                    OPENVERSE_AUDIO_URL,
                    params={"q": query, "categories": "music", "license": "cc0", "page_size": 20},
                    headers=headers,
                    timeout=20,
                )
                response.raise_for_status()
                results = [
                    item
                    for item in response.json().get("results", [])
                    if item.get("url")
                    and str(item.get("license") or "cc0").lower() == "cc0"
                ]
                if not results:
                    continue

                long_tracks = [
                    item for item in results
                    if self._duration(item) >= 25
                ]
                for track in (long_tracks or results)[:5]:
                    url = track["url"]
                    output_path = os.path.join(
                        output_dir, f"music_{hashlib.md5(url.encode()).hexdigest()[:10]}.audio"
                    )
                    try:
                        audio = requests.get(
                            url, headers=headers, stream=True, timeout=(5, 45)
                        )
                        audio.raise_for_status()
                        content_type = audio.headers.get("Content-Type", "").lower()
                        if "text/html" in content_type:
                            continue
                        downloaded = 0
                        with open(output_path, "wb") as file:
                            for chunk in audio.iter_content(chunk_size=64 * 1024):
                                if not chunk:
                                    continue
                                downloaded += len(chunk)
                                if downloaded > MAX_MUSIC_BYTES:
                                    raise ValueError("CC0 music file exceeded 40 MB")
                                file.write(chunk)
                        if not downloaded:
                            os.remove(output_path)
                            continue

                        with open(
                            os.path.join(output_dir, "music_source.json"),
                            "w",
                            encoding="utf-8",
                        ) as file:
                            json.dump(
                                {
                                    "title": track.get("title") or "Untitled CC0 music",
                                    "creator": track.get("creator") or "Unknown",
                                    "source_url": track.get("foreign_landing_url")
                                    or track.get("detail_url")
                                    or url,
                                    "license": "CC0",
                                    "license_url": track.get("license_url") or CC0_LICENSE_URL,
                                    "search_query": query,
                                },
                                file,
                                ensure_ascii=False,
                                indent=2,
                            )
                        print(f"  Selected free CC0 music for '{query}'")
                        return output_path
                    except Exception as exc:
                        try:
                            os.remove(output_path)
                        except OSError:
                            pass
                        print(f"  CC0 music download failed: {type(exc).__name__}")
            except Exception as exc:
                print(f"  Music search failed for '{query}': {type(exc).__name__}")

        print("  No suitable free CC0 music found; rendering without background music")
        return None

    @staticmethod
    def _duration(track: dict) -> float:
        try:
            return float(track.get("duration") or 0)
        except (TypeError, ValueError):
            return 0
