import tempfile
import unittest
from unittest.mock import Mock, patch

from src.silent_editor import _build_audio_filter
from src.sound_designer import SoundDesigner


class SceneAudioTests(unittest.TestCase):
    def test_scene_profile_changes_for_scene_topics(self):
        profile, _query, _filter = SoundDesigner._scene_profile("Cricket stadium match")
        self.assertEqual(profile, "sports")

        profile, _query, _filter = SoundDesigner._scene_profile("Monsoon rain in Mumbai")
        self.assertEqual(profile, "water")

        profile, _query, _filter = SoundDesigner._scene_profile("New AI computer chip")
        self.assertEqual(profile, "technology")

    def test_scene_sound_download_uses_generated_fallback_without_network_audio(self):
        search_response = Mock()
        search_response.json.return_value = {"results": []}
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "src.sound_designer.requests.get", return_value=search_response
        ) as get, patch("src.sound_designer.subprocess.run") as run:
            sounds = SoundDesigner().download_scene_sounds(
                [
                    {"search_query": "cricket stadium", "voiceover_text": "A close match"},
                    {"search_query": "heavy rain", "voiceover_text": "Monsoon floods"},
                ],
                temp_dir,
            )

        self.assertEqual(len(sounds), 2)
        self.assertIn("ambience_sports_", sounds[0])
        self.assertIn("ambience_water_", sounds[1])
        self.assertEqual(get.call_count, 2)
        self.assertEqual(run.call_count, 2)

    def test_audio_filter_mixes_music_and_scene_tracks_below_voice(self):
        graph = _build_audio_filter(2, [(3, 0.0, 5.0), (4, 5.0, 7.0)])

        self.assertIn("[2:a]volume=0.18[music]", graph)
        self.assertIn("[3:a]atrim=duration=5.000", graph)
        self.assertIn("[4:a]atrim=duration=7.000", graph)
        self.assertIn("adelay=delays=5000:all=1", graph)
        self.assertIn("amix=inputs=4:duration=first", graph)
        self.assertIn("alimiter=limit=0.95[aout]", graph)


if __name__ == "__main__":
    unittest.main()
