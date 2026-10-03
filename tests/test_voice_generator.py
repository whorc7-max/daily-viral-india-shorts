import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from src.voice_generator import (
    DEFAULT_ELEVENLABS_MODEL,
    DEFAULT_ELEVENLABS_VOICE_ID,
    VoiceGenerator,
    _split_chatterbox_text,
)


class VoiceGeneratorTests(unittest.TestCase):
    def test_chatterbox_text_splits_at_sentence_or_word_limit(self):
        chunks = _split_chatterbox_text(
            "एक दो तीन चार पाँच छह सात आठ नौ दस। ग्यारह बारह।",
            max_words=5,
        )

        self.assertEqual(
            chunks,
            ["एक दो तीन चार पाँच।", "छह सात आठ नौ दस।", "ग्यारह बारह।"],
        )
        self.assertTrue(all(len(chunk.split()) <= 5 for chunk in chunks))

    def test_elevenlabs_writes_audio_using_configured_voice(self):
        response = Mock(content=b"mp3-audio")
        requests = Mock()
        requests.post.return_value = response

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "voice.mp3")
            with (
                patch.dict(os.environ, {
                    "ELEVENLABS_API_KEY": "test-key",
                    "ELEVENLABS_VOICE_ID": "",
                    "TTS_BACKEND": "auto",
                    "TTS_REFERENCE_AUDIO_PATH": "",
                }),
                patch.dict("sys.modules", {"requests": requests}),
                patch(
                    "src.voice_generator.subprocess.run",
                    return_value=Mock(stdout="4.25\n"),
                ),
            ):
                duration = VoiceGenerator().generate("Namaste duniya", output_path)

            self.assertEqual(duration, 4.25)
            self.assertEqual(Path(output_path).read_bytes(), b"mp3-audio")

        requests.post.assert_called_once_with(
            f"https://api.elevenlabs.io/v1/text-to-speech/{DEFAULT_ELEVENLABS_VOICE_ID}",
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": "test-key"},
            json={"text": "Namaste duniya", "model_id": DEFAULT_ELEVENLABS_MODEL},
            timeout=120,
        )
        response.raise_for_status.assert_called_once_with()

    def test_missing_key_uses_edge_tts_fallback(self):
        generator = VoiceGenerator()
        with (
            patch.dict(os.environ, {
                "ELEVENLABS_API_KEY": "",
                "TTS_BACKEND": "auto",
                "TTS_REFERENCE_AUDIO_PATH": "",
            }),
            patch.object(generator, "_generate_edge", new_callable=AsyncMock) as edge,
            patch(
                "src.voice_generator.subprocess.run",
                return_value=Mock(stdout="5.5\n"),
            ),
        ):
            duration = generator.generate("Namaste duniya", "voice.mp3")

        self.assertEqual(duration, 5.5)
        edge.assert_awaited_once_with("Namaste duniya", "voice.mp3")

    def test_elevenlabs_error_does_not_silently_switch_voices(self):
        response = Mock(content=b"")
        response.raise_for_status.side_effect = RuntimeError("API request failed")
        requests = Mock()
        requests.post.return_value = response
        generator = VoiceGenerator()

        with (
            patch.dict(os.environ, {
                "ELEVENLABS_API_KEY": "test-key",
                "TTS_BACKEND": "auto",
                "TTS_REFERENCE_AUDIO_PATH": "",
            }),
            patch.dict("sys.modules", {"requests": requests}),
            patch.object(generator, "_generate_edge", new_callable=AsyncMock) as edge,
        ):
            with self.assertRaisesRegex(RuntimeError, "API request failed"):
                generator.generate("Namaste duniya", "voice.mp3")

        edge.assert_not_awaited()
        requests.post.assert_called_once()

    def test_default_voice_id_is_rahul_s(self):
        self.assertEqual(DEFAULT_ELEVENLABS_VOICE_ID, "2cdvnKJ5TZi631y5PN1s")

    def test_chatterbox_uses_private_reference_and_hindi(self):
        torch = Mock()
        torch.cuda.is_available.return_value = False
        torch.backends.mps.is_available.return_value = False
        torchaudio = Mock()
        generated_audio = Mock()
        generated_audio.detach.return_value = generated_audio
        generated_audio.cpu.return_value = generated_audio
        model = Mock(sr=24000)

        def generate(text, language_id, audio_prompt_path):
            self.assertEqual(text, "Namaste duniya")
            self.assertEqual(language_id, "hi")
            self.assertTrue(Path(audio_prompt_path).is_file())
            return generated_audio

        model.generate.side_effect = generate
        chatterbox_class = Mock()
        chatterbox_class.from_pretrained.return_value = model
        chatterbox_module = Mock()
        chatterbox_module.__path__ = []
        mtl_module = Mock(ChatterboxMultilingualTTS=chatterbox_class)

        def fake_subprocess(args, **kwargs):
            if args[0] == "ffmpeg":
                Path(args[-1]).write_bytes(b"audio")
                return Mock()
            return Mock(stdout="2.5\n")

        def fake_save(path, audio, sample_rate):
            Path(path).write_bytes(b"wav-audio")

        with tempfile.TemporaryDirectory() as temp_dir:
            reference_path = str(Path(temp_dir) / "recording.mp3")
            output_path = str(Path(temp_dir) / "voice.mp3")
            Path(reference_path).write_bytes(b"reference-audio")
            with (
                patch.dict(os.environ, {
                    "TTS_BACKEND": "chatterbox",
                    "TTS_REFERENCE_AUDIO_PATH": reference_path,
                    "CHATTERBOX_DEVICE": "auto",
                    "ELEVENLABS_API_KEY": "",
                }),
                patch.dict("sys.modules", {
                    "torch": torch,
                    "torchaudio": torchaudio,
                    "chatterbox": chatterbox_module,
                    "chatterbox.mtl_tts": mtl_module,
                }),
                patch("src.voice_generator.subprocess.run", side_effect=fake_subprocess),
            ):
                torchaudio.save.side_effect = fake_save
                duration = VoiceGenerator().generate("Namaste duniya", output_path)

            self.assertEqual(duration, 2.5)
            self.assertEqual(Path(output_path).read_bytes(), b"audio")

        chatterbox_class.from_pretrained.assert_called_once_with(device="cpu", t3_model="v3")
        model.generate.assert_called_once()
        torchaudio.save.assert_called_once()

    def test_chatterbox_requires_existing_reference_audio(self):
        generator = VoiceGenerator()
        with (
            patch.dict(os.environ, {
                "TTS_BACKEND": "chatterbox",
                "TTS_REFERENCE_AUDIO_PATH": "/missing/reference.wav",
                "ELEVENLABS_API_KEY": "",
            }),
            patch.object(generator, "_generate_edge", new_callable=AsyncMock) as edge,
        ):
            with self.assertRaises(FileNotFoundError):
                generator.generate("Namaste duniya", "voice.mp3")

        edge.assert_not_awaited()

    def test_chatterbox_reuses_reference_across_short_speech_chunks(self):
        torch = Mock()
        torch.cuda.is_available.return_value = False
        torch.backends.mps.is_available.return_value = False
        torch.float32 = "float32"
        torch.zeros.return_value = Mock(name="silence")
        combined_audio = Mock(name="combined-audio")
        torch.cat.return_value = combined_audio
        torchaudio = Mock()
        generated_audio = Mock()
        generated_audio.shape = (1, 24000)
        generated_audio.dtype = "float32"
        generated_audio.device = "cpu"
        generated_audio.detach.return_value = generated_audio
        generated_audio.cpu.return_value = generated_audio
        model = Mock(sr=24000)
        model.generate.return_value = generated_audio
        chatterbox_class = Mock()
        chatterbox_class.from_pretrained.return_value = model
        chatterbox_module = Mock()
        chatterbox_module.__path__ = []
        mtl_module = Mock(ChatterboxMultilingualTTS=chatterbox_class)

        def fake_subprocess(args, **kwargs):
            if args[0] == "ffmpeg":
                Path(args[-1]).write_bytes(b"audio")
                return Mock()
            return Mock(stdout="20.0\n")

        with tempfile.TemporaryDirectory() as temp_dir:
            reference_path = str(Path(temp_dir) / "recording.mp3")
            output_path = str(Path(temp_dir) / "voice.mp3")
            Path(reference_path).write_bytes(b"reference-audio")
            text = " ".join(f"शब्द{index}" for index in range(85))
            with (
                patch.dict(os.environ, {
                    "TTS_BACKEND": "chatterbox",
                    "TTS_REFERENCE_AUDIO_PATH": reference_path,
                    "CHATTERBOX_DEVICE": "auto",
                    "ELEVENLABS_API_KEY": "",
                }),
                patch.dict("sys.modules", {
                    "torch": torch,
                    "torchaudio": torchaudio,
                    "chatterbox": chatterbox_module,
                    "chatterbox.mtl_tts": mtl_module,
                }),
                patch("src.voice_generator.subprocess.run", side_effect=fake_subprocess),
            ):
                duration = VoiceGenerator().generate(text, output_path)

        self.assertEqual(duration, 20.0)
        self.assertEqual(model.generate.call_count, 3)
        calls = model.generate.call_args_list
        self.assertTrue(calls[0].kwargs["audio_prompt_path"].endswith("reference.wav"))
        self.assertIsNone(calls[1].kwargs["audio_prompt_path"])
        self.assertIsNone(calls[2].kwargs["audio_prompt_path"])
        self.assertTrue(all(c.kwargs["language_id"] == "hi" for c in calls))
        self.assertEqual(len(torch.cat.call_args.args[0]), 5)
        self.assertEqual(torch.cat.call_args.kwargs["dim"], -1)


if __name__ == "__main__":
    unittest.main()
