import asyncio
import os
import subprocess
import tempfile
import time


VOICE_NAME = os.environ.get("TTS_VOICE", "hi-IN-MadhurNeural")
VOICE_RATE = os.environ.get("TTS_RATE", "+0%")
DEFAULT_ELEVENLABS_VOICE_ID = "2cdvnKJ5TZi631y5PN1s"
DEFAULT_ELEVENLABS_MODEL = "eleven_multilingual_v2"


class VoiceGenerator:
    def generate(self, text: str, output_path: str) -> float:
        api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        backend = os.environ.get("TTS_BACKEND", "auto").strip().lower()
        reference_path = os.environ.get("TTS_REFERENCE_AUDIO_PATH", "").strip()

        if backend == "chatterbox" or (backend == "auto" and reference_path):
            if not reference_path:
                raise RuntimeError("TTS_REFERENCE_AUDIO_PATH is required for Chatterbox")
            if not os.path.isfile(reference_path):
                raise FileNotFoundError(f"TTS reference audio not found: {reference_path}")
            print("Generating Hindi voice with the local Chatterbox model...")
            self._generate_chatterbox(text, output_path, reference_path)
        elif backend == "elevenlabs" or (backend == "auto" and api_key):
            if not api_key:
                raise RuntimeError("ELEVENLABS_API_KEY is required for ElevenLabs")
            print("Generating Hindi voice with ElevenLabs...")
            self._generate_elevenlabs(text, output_path, api_key)
        elif backend in {"auto", "edge"}:
            print("ELEVENLABS_API_KEY is not set; using Edge TTS.")
            last_error = None
            for attempt in range(1, 4):
                try:
                    asyncio.run(self._generate_edge(text, output_path))
                    break
                except Exception as exc:
                    last_error = exc
                    print(f"Hindi voice attempt {attempt}/3 failed: {exc}")
                    if attempt < 3:
                        time.sleep(attempt * 2)
            else:
                raise RuntimeError(f"Hindi voice generation failed: {last_error}") from last_error
        else:
            raise ValueError(f"Unsupported TTS_BACKEND: {backend}")

        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", output_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())

    def _generate_elevenlabs(self, text: str, output_path: str, api_key: str):
        import requests

        voice_id = os.environ.get(
            "ELEVENLABS_VOICE_ID", DEFAULT_ELEVENLABS_VOICE_ID
        ).strip() or DEFAULT_ELEVENLABS_VOICE_ID
        model_id = os.environ.get(
            "ELEVENLABS_MODEL", DEFAULT_ELEVENLABS_MODEL
        ).strip() or DEFAULT_ELEVENLABS_MODEL
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": api_key},
            json={"text": text, "model_id": model_id},
            timeout=120,
        )
        response.raise_for_status()
        if not response.content:
            raise RuntimeError("ElevenLabs returned an empty audio response")
        with open(output_path, "wb") as audio_file:
            audio_file.write(response.content)

    def _generate_chatterbox(self, text: str, output_path: str, reference_path: str):
        import torch
        import torchaudio
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        device = os.environ.get("CHATTERBOX_DEVICE", "auto").strip().lower()
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

        with tempfile.TemporaryDirectory(prefix="chatterbox-") as temp_dir:
            normalized_reference = os.path.join(temp_dir, "reference.wav")
            generated_wav = os.path.join(temp_dir, "voice.wav")
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", reference_path, "-ac", "1", "-ar", "24000",
                    normalized_reference,
                ],
                check=True,
                capture_output=True,
            )
            model = ChatterboxMultilingualTTS.from_pretrained(
                device=device,
                t3_model="v3",
            )
            audio = model.generate(
                text,
                language_id="hi",
                audio_prompt_path=normalized_reference,
            )
            torchaudio.save(generated_wav, audio.detach().cpu(), model.sr)
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", generated_wav, "-codec:a", "libmp3lame", "-b:a", "128k",
                    output_path,
                ],
                check=True,
                capture_output=True,
            )

    async def _generate_edge(self, text: str, output_path: str):
        import edge_tts

        communicate = edge_tts.Communicate(text, VOICE_NAME, rate=VOICE_RATE)
        await communicate.save(output_path)
