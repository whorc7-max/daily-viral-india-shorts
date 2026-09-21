import hashlib
import os
import random
import subprocess

import requests


OPENVERSE_AUDIO_URL = "https://api.openverse.org/v1/audio/"


class MusicProvider:
    def _generated_fallback(self, output_dir: str) -> str | None:
        output_path = os.path.join(output_dir, "music_generated_ambient.mp3")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", "sine=frequency=196:duration=120",
                    "-f", "lavfi", "-i", "sine=frequency=293.66:duration=120",
                    "-filter_complex",
                    "[0:a]volume=0.035[a0];[1:a]volume=0.02[a1];"
                    "[a0][a1]amix=inputs=2:duration=longest,lowpass=f=900,"
                    "afade=t=in:st=0:d=2,afade=t=out:st=110:d=10",
                    "-q:a", "6", output_path,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("  Using generated royalty-free ambient fallback music")
            return output_path
        except Exception as exc:
            print(f"  Generated music fallback failed: {exc}")
            return None

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

        return self._generated_fallback(output_dir)
