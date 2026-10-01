import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from src.script_generator import (
    TREND_PAGE_URL,
    YOUTUBE_CATEGORIES,
    ScriptGenerator,
    _fallback_content,
)


def _response(items=None, content=b""):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"items": items or []}
    response.content = content
    return response


def _search_item(video_id, title, published, channel):
    return {
        "id": {"videoId": video_id},
        "snippet": {
            "title": title,
            "publishedAt": published.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "channelTitle": channel,
        },
    }


class YouTubeTrendTests(unittest.TestCase):
    def setUp(self):
        self.generator = ScriptGenerator.__new__(ScriptGenerator)
        self.generator.youtube_api_key = "test-youtube-key"
        self.generator.trend_source_urls = []

    def test_recent_youtube_videos_are_ranked_by_views_per_hour(self):
        now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
        older = now - timedelta(minutes=90)
        newer = now - timedelta(minutes=30)
        searches = [
            _response([_search_item("older", "Cricket surprise", older, "Sports Desk")]),
            _response([
                _search_item("newer", "Funny gaming moment", newer, "Game Hub"),
                _search_item("older", "Cricket surprise", older, "Sports Desk"),
            ]),
        ] + [_response() for _ in range(len(YOUTUBE_CATEGORIES) - 2)]
        statistics = _response([
            {"id": "older", "statistics": {"viewCount": "10000"}},
            {"id": "newer", "statistics": {"viewCount": "6000"}},
        ])

        with patch(
            "src.script_generator.requests.get",
            side_effect=[*searches, statistics],
        ) as get:
            candidates = self.generator._youtube_trends(now)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["url"], "https://www.youtube.com/watch?v=newer")
        self.assertIn("12,000 average views/hour since upload", candidates[0]["lead"])
        self.assertEqual(get.call_count, len(YOUTUBE_CATEGORIES) + 1)
        self.assertEqual(get.call_args_list[0].kwargs["params"]["regionCode"], "IN")
        self.assertEqual(get.call_args_list[0].kwargs["params"]["order"], "viewCount")
        self.assertEqual(
            get.call_args_list[0].kwargs["params"]["publishedAfter"],
            "2026-10-01T10:00:00Z",
        )

    def test_old_or_low_view_videos_are_not_called_viral_candidates(self):
        now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
        too_old = now - timedelta(hours=3)
        recent = now - timedelta(minutes=10)
        searches = [
            _response([_search_item("old", "Old upload", too_old, "Archive")]),
            _response([_search_item("low", "New upload", recent, "Small Channel")]),
        ] + [_response() for _ in range(len(YOUTUBE_CATEGORIES) - 2)]
        statistics = _response([{"id": "low", "statistics": {"viewCount": "999"}}])

        with patch(
            "src.script_generator.requests.get",
            side_effect=[*searches, statistics],
        ):
            candidates = self.generator._youtube_trends(now)

        self.assertEqual(candidates, [])

    def test_google_trends_is_fallback_when_youtube_key_is_missing(self):
        self.generator.youtube_api_key = ""
        self.generator.trend_source_urls = []
        feed = b"<rss><channel><item><title>India trend</title></item></channel></rss>"

        with patch("src.script_generator.requests.get", return_value=_response(content=feed)) as get:
            trends = self.generator._trends()

        self.assertEqual(trends, ["India trend"])
        self.assertEqual(self.generator.trend_source_urls, [TREND_PAGE_URL])
        self.assertEqual(get.call_count, 1)

    def test_fallback_script_is_fuller_and_keeps_scene_words_aligned(self):
        content = _fallback_content(["India trend"])
        script = content["voiceover_script"]

        self.assertGreaterEqual(len(script.split()), 240)
        self.assertEqual(
            " ".join(scene["voiceover_text"] for scene in content["visual_scenes"]),
            script,
        )


if __name__ == "__main__":
    unittest.main()
