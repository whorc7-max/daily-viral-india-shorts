import hashlib
import os
import random

import requests


OPENVERSE_AUDIO_URL = "https://api.openverse.org/v1/audio/"


class MusicProvider:
    def download(self, keywords: list[str], output_dir: str) -> str | None:
        queries = []
        if keywords:
            queries.append(" ".join(keywords[:2]))
        queries.extend(["ambient cinematic", "news background", "technology ambient"])
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
                results = [item.get("url") for item in response.json().get("results", [])]
                results = [url for url in results if url]
                if not results:
                    continue

                url = random.choice(results[:5])
                output_path = os.path.join(
                    output_dir, f"music_{hashlib.md5(url.encode()).hexdigest()[:10]}.mp3"
                )
                audio = requests.get(url, headers=headers, timeout=45)
                audio.raise_for_status()
                with open(output_path, "wb") as file:
                    file.write(audio.content)
                print(f"  Selected CC0 music for '{query}'")
                return output_path
            except Exception as exc:
                print(f"  Music search failed for '{query}': {exc}")

        return None

