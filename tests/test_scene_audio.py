import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from src.silent_editor import SilentVideoEditor, _build_audio_filter
from src.sound_designer import SoundDesigner


class SceneAudioTests(unittest.TestCase):
    def test_active_renderer_adds_no_visual_overlays_and_keeps_audio_mix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            voice_path = Path(temp_dir) / "voice.mp3"
            music_path = Path(temp_dir) / "music.audio"
            scene_audio_path = Path(temp_dir) / "scene.wav"
            image_path = Path(temp_dir) / "background.png"
            output_path = Path(temp_dir) / "final.mp4"
            for path in (voice_path, music_path, scene_audio_path):
                path.touch()
            Image.new("RGB", (80, 80), (42, 128, 107)).save(image_path)

            commands = []

            def fake_ffmpeg(command, **_kwargs):
                commands.append(command)
                Path(command[-1]).touch()

            with patch("src.silent_editor.subprocess.run", side_effect=fake_ffmpeg):
                SilentVideoEditor(temp_dir).compose(
                    image_paths=[str(image_path)],
                    script="A bright mountain view.",
                    output_path=str(output_path),
                    target_duration=2,
                    voice_path=str(voice_path),
                    music_path=str(music_path),
                    scene_specs=[{"voiceover_text": "A bright mountain view."}],
                    scene_audio_paths=[str(scene_audio_path)],
                )

            with Image.open(Path(temp_dir) / "scenes" / "background_000.png") as frame:
                self.assertEqual(frame.getpixel((540, 110)), (42, 128, 107))
                self.assertEqual(frame.getpixel((540, 1842)), (42, 128, 107))

        video_command = commands[0]
        video_filter = video_command[video_command.index("-filter_complex") + 1]
        self.assertEqual(video_command.count("-i"), 1)
        self.assertEqual(
            video_filter,
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,setsar=1,fps=30,format=yuv420p[v]",
        )
        command_text = " ".join(part for command in commands for part in command).lower()
        self.assertNotRegex(
            command_text,
            r"\b(drawtext|overlay|subtitles|ass|caption|watermark|progress)\b",
        )

        audio_command = commands[-1]
        audio_filter = audio_command[audio_command.index("-filter_complex") + 1]
        self.assertIn(str(music_path), audio_command)
        self.assertIn(str(scene_audio_path), audio_command)
        self.assertIn("[2:a]volume=0.18[music]", audio_filter)
        self.assertIn("[3:a]atrim=duration=2.000", audio_filter)
        self.assertIn("afade=t=in:st=0:d=0.600", audio_filter)
        self.assertIn("afade=t=out:st=1.400:d=0.600", audio_filter)
        self.assertIn("amix=inputs=3:duration=first", audio_filter)

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
