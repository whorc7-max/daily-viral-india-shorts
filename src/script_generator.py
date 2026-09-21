import json
import os
import re
import xml.etree.ElementTree as ET

import requests

try:
    from google import genai
    from google.genai import types
except ImportError as exc:  # pragma: no cover - dependency is installed in Actions
    raise RuntimeError("google-genai is required to generate scripts") from exc


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
TREND_URL = "https://trends.google.com/trending/rss?geo=IN"


def _clean_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    return json.loads(text)


class ScriptGenerator:
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required to generate Hindi scripts")

    def _trends(self) -> list[str]:
        try:
            response = requests.get(TREND_URL, timeout=20)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            titles = [item.findtext("title") for item in root.findall(".//item")]
            return [title.strip() for title in titles if title and title.strip()][:12]
        except Exception as exc:
            print(f"Trend feed unavailable: {exc}")
            return ["भारत और दुनिया की आज की महत्वपूर्ण खबरें"]

    def generate(self) -> dict:
        trends = self._trends()
        prompt = f"""
You are the editorial producer for the Hindi YouTube Shorts channel Daily Viral India.
Create exactly one original Hindi YouTube Short for Indian viewers.

Use these current India trend leads, but verify claims and never invent details:
{json.dumps(trends, ensure_ascii=False)}

Return ONLY valid JSON with these fields:
title, description, tags, voiceover_script, visual_keywords, visual_scenes, source_urls, duration_seconds

Rules:
- Write natural Hindi in Devanagari, approximately 90-130 words.
- Make the script natural for a clear Hindi voiceover and readable captions.
- Hook viewers in the first sentence and keep sentences short for readable captions.
- Choose one topic only and add meaningful original commentary.
- Separate confirmed facts from rumours; avoid defamation, unsafe advice, and political claims without reliable sourcing.
- Do not copy any source wording, thumbnail, footage, music, or song.
- visual_keywords must contain 4-6 short English search terms for royalty-cleared stock images.
- visual_scenes must contain 6-8 objects in narration order. Each object must have:
  {"search_query": "2-5 English words for a relevant real image", "image_prompt": "a detailed vertical 9:16 visual prompt"}.
- Make each scene match the sentence or beat it illustrates; do not repeat the same generic image prompt.
- image_prompt must describe a safe, text-free editorial visual with no logos, watermarks, or invented people.
- source_urls must contain the Google Trends India URL and any specific source URL you can verify; never fabricate URLs.
- duration_seconds must be between 45 and 60.
- description must include a brief disclosure that the Short uses original commentary and licensed/stock visuals.
""".strip()

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )
        content = _clean_json(response.text)

        required = (
            "title",
            "description",
            "tags",
            "voiceover_script",
            "visual_keywords",
            "visual_scenes",
            "source_urls",
        )
        missing = [key for key in required if not content.get(key)]
        if missing:
            raise ValueError(f"Gemini response missing fields: {', '.join(missing)}")

        content["duration_seconds"] = min(
            60, max(45, int(content.get("duration_seconds", 55)))
        )
        tags = content["tags"] if isinstance(content["tags"], list) else [content["tags"]]
        visual_keywords = (
            content["visual_keywords"]
            if isinstance(content["visual_keywords"], list)
            else [content["visual_keywords"]]
        )
        source_urls = (
            content["source_urls"]
            if isinstance(content["source_urls"], list)
            else [content["source_urls"]]
        )
        content["tags"] = [str(tag) for tag in tags][:15]
        content["visual_keywords"] = [str(term) for term in visual_keywords][:6]
        scenes = content["visual_scenes"] if isinstance(content["visual_scenes"], list) else []
        cleaned_scenes = []
        for scene in scenes[:8]:
            if not isinstance(scene, dict):
                continue
            query = str(scene.get("search_query", "")).strip()
            prompt = str(scene.get("image_prompt", "")).strip()
            if query and prompt:
                cleaned_scenes.append({"search_query": query, "image_prompt": prompt})
        if not cleaned_scenes:
            raise ValueError("Gemini response did not include usable visual_scenes")
        content["visual_scenes"] = cleaned_scenes
        content["source_urls"] = list(dict.fromkeys([
            "https://trends.google.com/trending?geo=IN",
            *[str(url) for url in source_urls],
        ]))
        return content
