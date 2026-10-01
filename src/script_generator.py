import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET

import requests

try:
    from google import genai
    from google.genai import types
except ImportError as exc:  # pragma: no cover - dependency is installed in Actions
    raise RuntimeError("google-genai is required to generate scripts") from exc


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_API_KEYS = list(dict.fromkeys(
    key.strip()
    for key in os.environ.get("GEMINI_API_KEYS", "").split(",")
    if key.strip()
))
if GEMINI_API_KEY and GEMINI_API_KEY not in GEMINI_API_KEYS:
    GEMINI_API_KEYS.append(GEMINI_API_KEY)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
TREND_URL = "https://trends.google.com/trending/rss?geo=IN"
TREND_PAGE_URL = "https://trends.google.com/trending?geo=IN"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_WINDOW = timedelta(hours=2)
YOUTUBE_MIN_VIEWS = 1000
YOUTUBE_CATEGORIES = (
    ("Comedy and memes", "23", "funny|comedy|memes|prank|मजेदार|कॉमेडी|मीम|वायरल"),
    ("Emotional and heart-touching", "22", "emotional|heart touching|inspiring|story|भावुक|दिल छू लेने वाला|कहानी"),
    ("Amazing, surprising and viral moments", "24", "viral|amazing|surprising|interesting|moment|वायरल|हैरान|अद्भुत"),
    ("Sports", "17", "sports|cricket|football|match|highlight|खेल|क्रिकेट|फुटबॉल"),
    ("Gaming", "20", "gaming|gameplay|esports|game|गेमिंग|गेमप्ले"),
    ("Movies and entertainment", "1", "movie|film|trailer|cinema|Bollywood|फिल्म|बॉलीवुड"),
    ("Music trends", "10", "music|song|trending|viral|गाना|संगीत"),
    ("Celebrity and public-interest news", "25", "news|celebrity|India|viral|खबर|सेलिब्रिटी|वायरल"),
)


def _clean_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    return json.loads(text)


def _fallback_content(trends: list[str]) -> dict:
    topic = trends[0] if trends else "भारत में तेजी से उभरता लोकप्रिय विषय"
    topic = re.sub(r"^\[YouTube [^\]]+\]\s*", "", topic).split(" | ", 1)[0].strip(' "')
    sentences = [
        f"आज तेजी से ध्यान खींच रहा विषय है: {topic}।",
        "किसी वीडियो पर views तेजी से बढ़ना दर्शकों की रुचि का संकेत है, अपने आप में किसी दावे का प्रमाण नहीं।",
        "इस विषय को समझने के लिए मूल वीडियो का पूरा संदर्भ, तारीख और उपलब्ध पुष्टि देखना जरूरी है।",
        "किसी छोटे clip से पूरी घटना या किसी व्यक्ति की मंशा तय करना सही नहीं होगा।",
        "अगर यह खेल, मनोरंजन, संगीत या गेमिंग का पल है, तो मूल संदर्भ और संबंधित लोगों की प्रतिक्रिया अहम है।",
        "अगर इसमें कोई सार्वजनिक दावा या संवेदनशील खबर है, तो उसे भरोसेमंद स्रोतों से जांचे बिना सच न कहें।",
        "तेजी से फैलने वाले clips कभी-कभी पूरी कहानी नहीं दिखाते, इसलिए संदर्भ को नजरअंदाज न करें।",
        "आज हम उपलब्ध जानकारी को आसान भाषा में रखेंगे और अनुमान को तथ्य की तरह पेश नहीं करेंगे।",
        "इस तरह के पलों में दर्शकों की प्रतिक्रिया भी कहानी का हिस्सा बन जाती है।",
        "किसी मजेदार या हैरान करने वाले पल को साझा करते समय उसमें शामिल लोगों की गरिमा का ध्यान रखें।",
        "लोकप्रियता बदलती रहती है, लेकिन सही संदर्भ किसी भी trend को समझने में मदद करता है।",
        "हम किसी मूल video की आवाज, script या footage की नकल किए बिना अपनी commentary दे रहे हैं।",
        "नई पुष्टि सामने आए तो इस विषय की समझ भी बदल सकती है, इसलिए अपडेट पर नजर रखना बेहतर है।",
        "आपको इस trend का सबसे दिलचस्प पहलू क्या लगा, अपनी राय बताइए।",
        "ऐसे ही तेजी से उभरते विषयों पर साफ और जिम्मेदार हिंदी updates के लिए जुड़े रहिए।",
        "किसी भी चर्चा को समझते समय उपलब्ध तथ्यों के साथ यह भी देखना चाहिए कि अभी कौन-सी बातें अज्ञात हैं।",
    ]
    keywords = ["India trending topic", "viral moment", "popular culture", "people reaction"]
    return {
        "title": f"{topic} | आज की चर्चा",
        "description": (
            "यह Short मौलिक हिंदी commentary और licensed/stock visuals के साथ बनाया गया है। "
            "यह प्रारंभिक trend summary है; आधिकारिक स्रोतों से पुष्टि करें।"
        ),
        "tags": ["Hindi Shorts", "India Trends", "Viral Moments", "Daily Viral India"],
        "voiceover_script": " ".join(sentences),
        "visual_keywords": keywords,
        "visual_scenes": [
            {
                "search_query": keywords[index % len(keywords)],
                "image_prompt": f"Editorial vertical visual illustrating: {sentence}",
                "voiceover_text": sentence,
            }
            for index, sentence in enumerate(sentences)
        ],
        "source_urls": [TREND_PAGE_URL],
        "duration_seconds": 150,
    }


class ScriptGenerator:
    def __init__(self):
        self.youtube_api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
        self.trend_source_urls = []
        self.clients = []
        for api_key in GEMINI_API_KEYS:
            try:
                self.clients.append(genai.Client(api_key=api_key))
            except Exception as exc:
                print(f"Gemini client unavailable: {exc}")

    def _youtube_trends(self, now: datetime | None = None) -> list[dict]:
        if not self.youtube_api_key:
            return []

        now = now or datetime.now(timezone.utc)
        now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
        window_start = now - YOUTUBE_WINDOW
        published_after = window_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        found = {}

        for category, category_id, query in YOUTUBE_CATEGORIES:
            try:
                response = requests.get(
                    YOUTUBE_SEARCH_URL,
                    params={
                        "key": self.youtube_api_key,
                        "part": "snippet",
                        "type": "video",
                        "regionCode": "IN",
                        "order": "viewCount",
                        "publishedAfter": published_after,
                        "videoCategoryId": category_id,
                        "maxResults": 5,
                        "q": query,
                    },
                    timeout=(5, 15),
                )
                response.raise_for_status()
                items = response.json().get("items", [])
            except Exception as exc:
                print(f"YouTube {category} search unavailable: {type(exc).__name__}")
                continue

            for item in items:
                video_id = str(item.get("id", {}).get("videoId") or "").strip()
                snippet = item.get("snippet") or {}
                published_at = str(snippet.get("publishedAt") or "")
                if not video_id or not published_at:
                    continue
                try:
                    published = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    ).astimezone(timezone.utc)
                except ValueError:
                    continue
                if published < window_start or published > now:
                    continue
                found.setdefault(video_id, {
                    "category": category,
                    "title": str(snippet.get("title") or "").strip(),
                    "channel": str(snippet.get("channelTitle") or "").strip(),
                    "published": published,
                })

        if not found:
            return []

        try:
            response = requests.get(
                YOUTUBE_VIDEOS_URL,
                params={
                    "key": self.youtube_api_key,
                    "part": "snippet,statistics",
                    "id": ",".join(found),
                },
                timeout=(5, 15),
            )
            response.raise_for_status()
            items = response.json().get("items", [])
        except Exception as exc:
            print(f"YouTube view counts unavailable: {type(exc).__name__}")
            return []

        candidates = []
        for item in items:
            video_id = str(item.get("id") or "")
            candidate = found.get(video_id)
            if not candidate:
                continue
            try:
                views = int((item.get("statistics") or {}).get("viewCount", 0))
            except (TypeError, ValueError):
                continue
            age_seconds = (now - candidate["published"]).total_seconds()
            if views < YOUTUBE_MIN_VIEWS or age_seconds <= 0 or age_seconds > YOUTUBE_WINDOW.total_seconds():
                continue

            age_minutes = max(1, int(age_seconds // 60))
            views_per_hour = int(views * 3600 / age_seconds)
            title = candidate["title"] or str((item.get("snippet") or {}).get("title") or "").strip()
            channel = candidate["channel"] or str((item.get("snippet") or {}).get("channelTitle") or "").strip()
            url = f"https://www.youtube.com/watch?v={video_id}"
            candidates.append({
                "url": url,
                "views_per_hour": views_per_hour,
                "lead": (
                    f"[YouTube {candidate['category']}] {title} | {channel}, "
                    f"{views:,} views in {age_minutes} min "
                    f"(~{views_per_hour:,} average views/hour since upload) | {url}"
                ),
            })

        candidates.sort(key=lambda candidate: candidate["views_per_hour"], reverse=True)
        return candidates[:12]

    def _trends(self) -> list[str]:
        self.trend_source_urls = []
        candidates = self._youtube_trends()
        if candidates:
            self.trend_source_urls = [candidate["url"] for candidate in candidates]
            print(
                f"Found {len(candidates)} YouTube videos from the past two hours "
                f"with at least {YOUTUBE_MIN_VIEWS:,} views"
            )
            return [candidate["lead"] for candidate in candidates]

        if self.youtube_api_key:
            print("No qualifying recent YouTube videos; falling back to Google Trends")
        else:
            print("YOUTUBE_API_KEY is not set; falling back to Google Trends")

        try:
            response = requests.get(TREND_URL, timeout=20)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            titles = [item.findtext("title") for item in root.findall(".//item")]
            trends = [title.strip() for title in titles if title and title.strip()][:12]
            self.trend_source_urls = [TREND_PAGE_URL]
            return trends or ["भारत में तेजी से उभरता लोकप्रिय विषय"]
        except Exception as exc:
            print(f"Trend feed unavailable: {exc}")
            self.trend_source_urls = [TREND_PAGE_URL]
            return ["भारत में तेजी से उभरता लोकप्रिय विषय"]

    def generate(self) -> dict:
        trends = self._trends()
        trend_source_type = (
            "YouTube videos published in the previous two hours, ranked by average views per hour since upload"
            if any("youtube.com/watch" in url for url in self.trend_source_urls)
            else "Google Trends fallback"
        )
        prompt = f"""
You are the editorial producer for the Hindi YouTube Shorts channel Daily Viral India.
Create exactly one original Hindi YouTube Short for Indian viewers.

Trend source: {trend_source_type}
Use these current India trend leads, but verify claims and never invent details:
{json.dumps(trends, ensure_ascii=False)}

Return ONLY valid JSON with these fields:
title, description, tags, voiceover_script, visual_keywords, visual_scenes, source_urls, duration_seconds

Rules:
- Write natural Hindi in Devanagari, approximately 240-330 words at a slightly brisk speaking pace (Edge TTS rate +10%) so the voiceover stays near 120-180 seconds.
- Make the script natural for a clear Hindi voiceover; narration is not displayed as on-screen text.
- Hook viewers in the first sentence and keep sentences short for visual pacing.
- Choose from funny/comedy, emotional/heart-touching, amazing/surprising, viral moments, interesting incidents, sports, gaming, movies/entertainment, music trends, celebrity/public-interest news, or memes/internet trends.
- When YouTube candidates are supplied, choose one topic from those candidates and prioritize the highest average views-per-hour-since-upload signal; call it "viral" only when the available evidence supports that description.
- Treat views and view velocity as a discovery signal, not proof that a video's claims are true; add original commentary and do not copy its script, audio, or footage.
- Choose one topic only and add meaningful original commentary.
- Separate confirmed facts from rumours; avoid defamation, unsafe advice, and political claims without reliable sourcing.
- Do not copy any source wording, thumbnail, footage, music, or song.
- visual_keywords must contain 4-6 short English search terms for royalty-cleared stock video footage.
- visual_scenes must contain 10-24 short visual beats in narration order. Each object must have:
  {{"voiceover_text": "the exact Hindi words spoken during this beat", "search_query": "2-5 concrete English words for the exact subject", "image_prompt": "a detailed vertical 9:16 visual prompt"}}.
- Split the narration at natural meaning changes, usually every 4-14 spoken words, so the visual changes when the spoken idea changes.
- The voiceover_text values, joined in order, must cover the full voiceover_script without skipping or inventing words.
- Keep named people, teams, places, and objects in search_query. For abstract claims, use a concrete visual query that proves the idea, such as "Virat Kohli charity" for a line about his kindness.
- Make every beat match its exact voiceover_text; do not repeat generic visuals.
- image_prompt must describe a safe, text-free editorial visual with no logos, watermarks, or invented people.
- source_urls must include the supplied YouTube candidate URLs when present, otherwise the Google Trends India URL, plus only specific source URLs you can verify; never fabricate URLs.
- duration_seconds must be between 120 and 180.
- description must include a brief disclosure that the Short uses original commentary and licensed/stock video visuals.
""".strip()

        if not self.clients:
            print("GEMINI_API_KEY is not set; using the safe script fallback")
            fallback = _fallback_content(trends)
            fallback["source_urls"] = self.trend_source_urls or fallback["source_urls"]
            return fallback

        content = None
        for client_index, client in enumerate(self.clients, start=1):
            for attempt in range(1, 4):
                try:
                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.7,
                            response_mime_type="application/json",
                        ),
                    )
                    content = _clean_json(response.text)
                    break
                except Exception as exc:
                    print(
                        f"Gemini key {client_index}/{len(self.clients)} "
                        f"attempt {attempt}/3 failed: {exc}"
                    )
                    if attempt < 3:
                        time.sleep(attempt * 3)
            if content is not None:
                break

        if content is None:
            print("Gemini unavailable; using the safe script fallback")
            fallback = _fallback_content(trends)
            fallback["source_urls"] = self.trend_source_urls or fallback["source_urls"]
            return fallback

        required = (
            "title",
            "description",
            "tags",
            "voiceover_script",
            "visual_keywords",
            "source_urls",
        )
        missing = [key for key in required if not content.get(key)]
        if missing:
            raise ValueError(f"Gemini response missing fields: {', '.join(missing)}")

        content["duration_seconds"] = min(
            180, max(120, int(content.get("duration_seconds", 150)))
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
        sentence_parts = [
            part.strip()
            for part in re.split(r"(?<=[।.!?])\s+", content["voiceover_script"].strip())
            if part.strip()
        ] or [content["title"]]
        scenes = content.get("visual_scenes", [])
        scenes = scenes if isinstance(scenes, list) else []
        cleaned_scenes = []
        for scene in scenes[:24]:
            if not isinstance(scene, dict):
                continue
            query = str(scene.get("search_query", "")).strip()
            prompt = str(scene.get("image_prompt", "")).strip()
            voiceover_text = str(
                scene.get("voiceover_text")
                or scene.get("narration")
                or scene.get("text")
                or ""
            ).strip()
            if query and prompt:
                cleaned_scenes.append({
                    "search_query": query,
                    "image_prompt": prompt,
                    "voiceover_text": voiceover_text,
                })

        script_word_count = len(content["voiceover_script"].split())
        beat_word_count = sum(
            len(scene["voiceover_text"].split())
            for scene in cleaned_scenes
            if scene["voiceover_text"]
        )
        has_complete_beats = (
            len(cleaned_scenes) >= 2
            and all(scene["voiceover_text"] for scene in cleaned_scenes)
            and beat_word_count >= max(1, int(script_word_count * 0.9))
        )

        if not has_complete_beats:
            keywords = content["visual_keywords"] or ["India news"]
            cleaned_scenes = [
                {
                    "search_query": str(keywords[index % len(keywords)]),
                    "image_prompt": (
                        f"Editorial visual about {keywords[index % len(keywords)]}, "
                        f"showing the idea: {part[:160]}"
                    ),
                    "voiceover_text": part,
                }
                for index, part in enumerate(sentence_parts)
            ]
        content["visual_scenes"] = cleaned_scenes
        content["source_urls"] = list(dict.fromkeys([
            *(self.trend_source_urls or [TREND_PAGE_URL]),
            *[str(url) for url in source_urls],
        ]))
        return content
