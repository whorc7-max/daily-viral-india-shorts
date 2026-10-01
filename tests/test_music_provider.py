import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.music_provider import MusicProvider


class MusicProviderTests(unittest.TestCase):
    def test_rain_topic_searches_for_free_romantic_monsoon_music(self):
        queries = MusicProvider._queries("Monsoon story", ["rain", "Mumbai"])

        self.assertEqual(queries[0], "romantic monsoon instrumental")
        self.assertIn("upbeat romantic rain instrumental", queries)

    def test_sports_topic_searches_for_energetic_instrumental(self):
        queries = MusicProvider._queries("Cricket upset", ["stadium", "match"])

        self.assertEqual(queries[0], "energetic sports instrumental")

    def test_downloads_authorized_topic_track_without_leaking_its_url(self):
        direct_url = "https://music.rightsholder.example/rain-song.mp3?token=private"
        catalog = {
            "tracks": [
                {
                    "title": "Licensed monsoon song",
                    "direct_url": direct_url,
                    "tags": ["rain", "monsoon", "romantic"],
                    "rights_holder": "Example Records",
                    "authorized_for_youtube": True,
                }
            ]
        }
        audio_response = Mock()
        audio_response.status_code = 200
        audio_response.url = direct_url
        audio_response.headers = {"Content-Type": "audio/mpeg"}
        audio_response.iter_content.return_value = [b"licensed audio"]

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"LICENSED_MUSIC_CATALOG_JSON": json.dumps(catalog)}
        ), patch("src.music_provider.requests.get", return_value=audio_response) as get:
            path = MusicProvider().download(["rain"], temp_dir, topic="Monsoon story")

            self.assertTrue(path)
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(get.call_args.args[0], direct_url)
            self.assertFalse(get.call_args.kwargs["allow_redirects"])
            with open(f"{temp_dir}/music_source.json", encoding="utf-8") as file:
                source = json.load(file)

        self.assertEqual(source["title"], "Licensed monsoon song")
        self.assertEqual(source["rights_holder"], "Example Records")
        self.assertNotIn("direct_url", source)
        self.assertNotIn("private", json.dumps(source))

    def test_y2mate_catalog_url_is_not_requested(self):
        catalog = {
            "tracks": [
                {
                    "title": "Licensed rain song",
                    "direct_url": "https://www.y2mate.com/download/song",
                    "tags": ["rain"],
                    "rights_holder": "Example Records",
                    "authorized_for_youtube": True,
                }
            ]
        }
        search_response = Mock()
        search_response.json.return_value = {"results": []}

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"LICENSED_MUSIC_CATALOG_JSON": json.dumps(catalog)}
        ), patch("src.music_provider.requests.get", return_value=search_response) as get:
            self.assertIsNone(
                MusicProvider().download(["rain"], temp_dir, topic="rain")
            )

        self.assertTrue(get.call_args_list)
        self.assertTrue(all(call.args[0].startswith("https://api.openverse.org/") for call in get.call_args_list))

    def test_downloads_cc0_track_and_records_its_source(self):
        search_response = Mock()
        search_response.json.return_value = {
            "results": [
                {
                    "url": "https://audio.example/monsoon-track.mp3",
                    "title": "Monsoon instrumental",
                    "creator": "Free Music Maker",
                    "license": "cc0",
                    "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                    "foreign_landing_url": "https://example.com/monsoon-track",
                    "duration": 90,
                }
            ]
        }
        audio_response = Mock()
        audio_response.headers = {"Content-Type": "audio/mpeg"}
        audio_response.iter_content.return_value = [b"audio bytes"]

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "src.music_provider.requests.get",
            side_effect=[search_response, audio_response],
        ) as get:
            path = MusicProvider().download(
                ["rain", "monsoon"], temp_dir, topic="Monsoon story"
            )

            self.assertTrue(path)
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(path.endswith(".audio"))
            self.assertEqual(get.call_args_list[0].kwargs["params"]["license"], "cc0")
            with open(f"{temp_dir}/music_source.json", encoding="utf-8") as file:
                source = json.load(file)

        self.assertEqual(source["title"], "Monsoon instrumental")
        self.assertEqual(source["license"], "CC0")
        self.assertEqual(source["source_url"], "https://example.com/monsoon-track")

    def test_rejects_non_cc0_result(self):
        search_response = Mock()
        search_response.json.return_value = {
            "results": [
                {"url": "https://audio.example/restricted.mp3", "license": "by-nc"}
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "src.music_provider.requests.get", return_value=search_response
        ) as get:
            path = MusicProvider().download(["rain"], temp_dir, topic="rain")

        self.assertIsNone(path)
        self.assertEqual(get.call_count, len(MusicProvider._queries("rain", ["rain"])))


if __name__ == "__main__":
    unittest.main()
