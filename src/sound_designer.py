import os
import glob
import hashlib
import re
import shutil
import subprocess
import requests
import random

BGM_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bgm")
OPENVERSE_AUDIO_URL = "https://api.openverse.org/v1/audio/"


class SoundDesigner:
    def __init__(self):
        pass

    @staticmethod
    def _scene_profile(text: str) -> tuple[str, str, str]:
        text = text.lower()
        profiles = [
            ("water", ("rain", "storm", "ocean", "sea", "river", "waterfall", "flood", "monsoon"), "rain water waves", "lowpass=f=850,tremolo=f=0.18:d=0.35"),
            ("nature", ("forest", "wildlife", "animal", "bird", "nature", "tree", "wildlife"), "forest birds wind", "highpass=f=350,lowpass=f=2800,tremolo=f=0.55:d=0.3"),
            ("sports", ("cricket", "football", "sport", "stadium", "match", "player", "team"), "stadium crowd cheering", "highpass=f=220,lowpass=f=2200,tremolo=f=0.8:d=0.22"),
            ("transport", ("train", "railway", "airport", "flight", "metro", "traffic", "road", "bus", "station"), "train traffic station ambience", "highpass=f=90,lowpass=f=1200,tremolo=f=0.22:d=0.22"),
            ("technology", ("technology", "artificial intelligence", " ai ", "computer", "chip", "robot", "science", "space", "nasa", "rocket"), "technology machine hum", "highpass=f=500,lowpass=f=2600,tremolo=f=0.3:d=0.2"),
            ("health", ("hospital", "health", "medical", "doctor", "medicine", "clinic"), "hospital room tone ambience", "highpass=f=400,lowpass=f=1700,tremolo=f=0.12:d=0.15"),
            ("celebration", ("festival", "culture", "temple", "dance", "celebration", "wedding"), "festival crowd ambience", "highpass=f=400,lowpass=f=3200,tremolo=f=1:d=0.18"),
            ("commerce", ("market", "economy", "stock", "business", "company", "finance", "bank", "inflation"), "market office crowd ambience", "highpass=f=120,lowpass=f=1000,tremolo=f=0.16:d=0.16"),
        ]
        for name, keywords, query, audio_filter in profiles:
            if any(keyword in text for keyword in keywords) or (
                name == "technology" and re.search(r"\bai\b", text)
            ):
                return name, query, audio_filter
        return "city", "city crowd street ambience", "highpass=f=100,lowpass=f=750,tremolo=f=0.18:d=0.2"

    def download_scene_sounds(self, scenes: list[dict], output_dir: str) -> list[str | None]:
        """Get a CC0 ambience bed for each scene, with an offline generated fallback."""
        os.makedirs(output_dir, exist_ok=True)
        cache: dict[str, str | None] = {}
        tracks = []

        for index, scene in enumerate(scenes or []):
            scene = scene if isinstance(scene, dict) else {"search_query": str(scene)}
            query_text = " ".join(
                str(scene.get(key) or "")
                for key in ("search_query", "voiceover_text", "image_prompt")
            ).strip()
            profile, profile_query, audio_filter = self._scene_profile(query_text)
            scene_query = str(scene.get("search_query") or "").strip()
            query = " ".join(part for part in (scene_query, profile_query, "ambience") if part)
            cache_key = query.lower()

            if cache_key not in cache:
                cache[cache_key] = self._download_cc0_ambience(query, output_dir)
                if not cache[cache_key]:
                    cache[cache_key] = self._generated_ambience(
                        profile, audio_filter, query, output_dir
                    )
            tracks.append(cache[cache_key])
            if cache[cache_key]:
                print(f"  Scene {index + 1}: {profile} ambience ready")
            else:
                print(f"  Scene {index + 1}: ambience unavailable")
        return tracks

    def _download_cc0_ambience(self, query: str, output_dir: str) -> str | None:
        headers = {"User-Agent": "DailyViralIndia/1.0"}
        try:
            response = requests.get(
                OPENVERSE_AUDIO_URL,
                params={"q": query, "categories": "sound_effect", "license": "cc0", "page_size": 8},
                headers=headers,
                timeout=(5, 12),
            )
            response.raise_for_status()
            results = [item for item in response.json().get("results", []) if item.get("url")]
            if not results:
                return None

            long_results = []
            for item in results:
                try:
                    if float(item.get("duration") or 0) >= 4:
                        long_results.append(item)
                except (TypeError, ValueError):
                    continue
            candidates = long_results or results
            seed = int(hashlib.md5(query.encode()).hexdigest(), 16)
            audio_url = random.Random(seed).choice(candidates[:5])["url"]
            output_path = os.path.join(
                output_dir, f"ambience_{hashlib.md5((query + audio_url).encode()).hexdigest()[:12]}.audio"
            )
            downloaded = 0
            with requests.get(audio_url, headers=headers, stream=True, timeout=(5, 20)) as audio_response:
                audio_response.raise_for_status()
                content_type = audio_response.headers.get("Content-Type", "").lower()
                if "text/html" in content_type:
                    return None
                with open(output_path, "wb") as audio_file:
                    for chunk in audio_response.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        downloaded += len(chunk)
                        if downloaded > 20 * 1024 * 1024:
                            raise ValueError("CC0 ambience file exceeded 20 MB")
                        audio_file.write(chunk)
            if downloaded:
                print(f"  Downloaded CC0 scene ambience for '{query}'")
                return output_path
        except Exception as exc:
            print(f"  CC0 ambience search failed for '{query}': {type(exc).__name__}")
        return None

    @staticmethod
    def _generated_ambience(profile: str, audio_filter: str, query: str, output_dir: str) -> str | None:
        digest = hashlib.md5(query.encode()).hexdigest()[:10]
        output_path = os.path.join(output_dir, f"ambience_{profile}_{digest}.wav")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "lavfi", "-i",
                    "anoisesrc=color=pink:duration=12:amplitude=0.22",
                    "-filter_complex",
                    f"[0:a]{audio_filter},afade=t=in:st=0:d=0.6,"
                    "afade=t=out:st=10.5:d=1.5[out]",
                    "-map", "[out]", "-ar", "44100", "-ac", "2",
                    "-c:a", "pcm_s16le", output_path,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return output_path
        except Exception as exc:
            print(f"  Generated {profile} ambience failed: {type(exc).__name__}")
            return None

    def get_local_fallback(self, keywords: list[str], output_dir: str) -> str | None:
        """Fallback method to grab a local BGM file if Openverse queries fail."""
        tracks = glob.glob(os.path.join(BGM_DIR, "*.mp3"))
        if not tracks:
            print("  [Fallback] No local bgm/*.mp3 files found.")
            return None
        seed = " ".join(keywords)
        idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(tracks)
        track = tracks[idx]
        print(f"  [Fallback] Selected local BGM: {os.path.basename(track)}")
        out = os.path.join(output_dir, "bg_music.mp3")
        shutil.copy2(track, out)
        return out

    def download_bgm(self, keywords: list[str], output_dir: str) -> str | None:
        """
        Attempts to search and download a CC0 background music track from Openverse.
        Falls back to local BGM files if search/download fails.
        """
        # Formulate search queries to try in order of specificity
        queries_to_try = []
        if keywords:
            # 1. Try first two keywords combined
            queries_to_try.append(" ".join(keywords[:2]))
            # 2. Try keywords individually
            for kw in keywords[:3]:
                queries_to_try.append(kw)
        
        # 3. Always add a generic fallback query at the end
        queries_to_try.extend(["lofi", "ambient", "cinematic", "science tech"])

        headers = {
            "User-Agent": "AutoYouShortsPipeline/3.0 (https://github.com/shahidswisdom/yt-shorts-automation)"
        }

        for q in queries_to_try:
            print(f"Searching Openverse for CC0 music with query: '{q}'")
            params = {
                "q": q,
                "categories": "music",
                "license": "cc0",
                "page_size": 20
            }
            try:
                resp = requests.get(OPENVERSE_AUDIO_URL, params=params, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    
                    valid_tracks = []
                    for track in results:
                        url = track.get("url")
                        if url:
                            valid_tracks.append(url)
                    
                    if valid_tracks:
                        chosen_url = random.choice(valid_tracks[:5])
                        print(f"Downloading BGM from Openverse: {chosen_url}")
                        
                        out_path = os.path.join(output_dir, "bg_music.mp3")
                        audio_resp = requests.get(chosen_url, headers=headers, stream=True, timeout=30)
                        audio_resp.raise_for_status()
                        with open(out_path, "wb") as f:
                            for chunk in audio_resp.iter_content(chunk_size=8192):
                                f.write(chunk)
                        return out_path
                    else:
                        print(f"No valid tracks found for '{q}'. Trying next query...")
            except Exception as e:
                print(f"Openverse BGM search error for '{q}': {e}")

        print("Falling back to local BGM...")
        return self.get_local_fallback(keywords, output_dir)

    def download_sfx(self, query: str, output_dir: str) -> str | None:
        """
        Searches and downloads a CC0 sound effect from Openverse.
        Falls back to simpler terms or transitions if not found.
        """
        # Formulate search queries to try in order of specificity
        queries_to_try = [query]
        # Split terms to try simpler keywords
        words = query.split()
        if len(words) > 1:
            queries_to_try.extend(words)
        
        # Add a generic transition sound effect as the ultimate fallback
        queries_to_try.extend(["whoosh", "swoosh", "transition click", "beep"])

        headers = {
            "User-Agent": "AutoYouShortsPipeline/3.0 (https://github.com/shahidswisdom/yt-shorts-automation)"
        }

        for q in queries_to_try:
            print(f"Searching Openverse for CC0 sound effect: '{q}'")
            params = {
                "q": q,
                "categories": "sound_effect",
                "license": "cc0",
                "page_size": 10
            }
            try:
                resp = requests.get(OPENVERSE_AUDIO_URL, params=params, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    
                    valid_sfx = []
                    for item in results:
                        url = item.get("url")
                        if url:
                            valid_sfx.append(url)
                    
                    if valid_sfx:
                        chosen_url = random.choice(valid_sfx[:3])
                        print(f"Downloading SFX from Openverse: {chosen_url}")
                        
                        # Create a safe filename hash
                        hash_name = hashlib.md5(query.encode()).hexdigest()[:8]
                        out_path = os.path.join(output_dir, f"sfx_{hash_name}.mp3")
                        
                        audio_resp = requests.get(chosen_url, headers=headers, stream=True, timeout=20)
                        audio_resp.raise_for_status()
                        with open(out_path, "wb") as f:
                            for chunk in audio_resp.iter_content(chunk_size=8192):
                                f.write(chunk)
                        return out_path
                    else:
                        print(f"No valid tracks found for SFX '{q}'. Trying next query...")
            except Exception as e:
                print(f"Failed to fetch sound effect '{q}' from Openverse: {e}")
        
        return None
