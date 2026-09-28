import json
import os
import re
import time
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


def _clean_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    return json.loads(text)


def _fallback_content(trends: list[str]) -> dict:
    topic = trends[0] if trends else "भारत और दुनिया की आज की महत्वपूर्ण खबरें"
    sentences = [
        f"आज की विस्तृत ट्रेंडिंग चर्चा का विषय है: {topic}।",
        "इस विषय ने देशभर में लोगों का ध्यान खींचा है और सोशल मीडिया पर भी इसकी चर्चा लगातार बढ़ रही है।",
        "सबसे पहले यह समझना जरूरी है कि इस मामले में अभी तक कौन सी जानकारी सामने आई है और कौन सी बातें केवल अनुमान हैं।",
        "उपलब्ध शुरुआती जानकारी के अनुसार, इस विषय का असर आम लोगों, संबंधित संस्थाओं और आने वाले फैसलों पर पड़ सकता है।",
        "इसी वजह से अलग-अलग लोग अपने अनुभव, सवाल और उम्मीदें साझा कर रहे हैं।",
        "हालांकि किसी वायरल दावे को सच मानने से पहले आधिकारिक बयान और विश्वसनीय रिपोर्ट देखना बेहद जरूरी है।",
        "इस कहानी का एक महत्वपूर्ण पहलू यह भी है कि इसका संबंध भारत में बदलती पसंद, तकनीक और सार्वजनिक चर्चा से जुड़ता है।",
        "आने वाले दिनों में नए अपडेट, आधिकारिक आंकड़े या संबंधित लोगों की प्रतिक्रिया तस्वीर को और साफ कर सकती है।",
        "दर्शकों के लिए सबसे सही तरीका यही है कि वे जल्दबाजी में निष्कर्ष न निकालें और खबर को जिम्मेदारी से साझा करें।",
        "हम इस विषय पर नजर बनाए रखेंगे और पुष्टि होने वाली महत्वपूर्ण जानकारी आपको सरल भाषा में बताते रहेंगे।",
        "आपके हिसाब से इस पूरे मामले का सबसे बड़ा असर किस क्षेत्र पर पड़ेगा, अपनी राय जरूर बताइए।",
        "इस विषय को समझने के लिए केवल एक वायरल पोस्ट पर निर्भर रहने के बजाय अलग-अलग विश्वसनीय स्रोतों की तुलना करना बेहतर रहेगा।",
        "अगर आने वाले दिनों में कोई नया आधिकारिक अपडेट आता है, तो उससे मौजूदा तस्वीर में बड़ा बदलाव भी हो सकता है।",
        "यही वजह है कि इस कहानी को लगातार अपडेट होने वाली खबर के रूप में देखना चाहिए, अंतिम निष्कर्ष के रूप में नहीं।",
        "हमारी कोशिश रहेगी कि आपको तेज खबर के साथ उसका संदर्भ, संभावित असर और जरूरी सावधानी भी समझाई जाए।",
        "वीडियो पसंद आए तो इसे साझा करें और ऐसे तथ्य आधारित अपडेट के लिए चैनल को फॉलो करना न भूलें।",
    ]
    keywords = ["India news", "breaking news", "digital news", "people discussion"]
    return {
        "title": f"{topic} | आज की चर्चा",
        "description": (
            "यह Short मौलिक हिंदी commentary और licensed/stock visuals के साथ बनाया गया है। "
            "यह प्रारंभिक trend summary है; आधिकारिक स्रोतों से पुष्टि करें।"
        ),
        "tags": ["Hindi News", "India News", "Shorts", "Daily Viral India"],
        "voiceover_script": " ".join(sentences),
        "visual_keywords": keywords,
        "visual_scenes": [
            {
                "search_query": keywords[index],
                "image_prompt": f"Editorial vertical visual illustrating: {sentence}",
                "voiceover_text": sentence,
            }
            for index, sentence in enumerate(sentences)
        ],
        "source_urls": ["https://trends.google.com/trending?geo=IN"],
        "duration_seconds": 150,
    }


class ScriptGenerator:
    def __init__(self):
        self.clients = []
        for api_key in GEMINI_API_KEYS:
            try:
                self.clients.append(genai.Client(api_key=api_key))
            except Exception as exc:
                print(f"Gemini client unavailable: {exc}")

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
- Write natural Hindi in Devanagari, approximately 200-270 words at normal speaking speed so the voiceover stays near 120-180 seconds.
- Make the script natural for a clear Hindi voiceover and readable captions.
- Hook viewers in the first sentence and keep sentences short for readable captions.
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
- source_urls must contain the Google Trends India URL and any specific source URL you can verify; never fabricate URLs.
- duration_seconds must be between 120 and 180.
- description must include a brief disclosure that the Short uses original commentary and licensed/stock video visuals.
""".strip()

        if not self.clients:
            print("GEMINI_API_KEY is not set; using the safe script fallback")
            return _fallback_content(trends)

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
            return _fallback_content(trends)

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
            "https://trends.google.com/trending?geo=IN",
            *[str(url) for url in source_urls],
        ]))
        return content
