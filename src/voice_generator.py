import asyncio
import os
import subprocess
import time

import edge_tts


VOICE_NAME = os.environ.get("TTS_VOICE", "hi-IN-MadhurNeural")


class VoiceGenerator:
    def generate(self, text: str, output_path: str) -> float:
        last_error = None
        for attempt in range(1, 4):
            try:
                asyncio.run(self._generate(text, output_path))
                break
            except Exception as exc:
                last_error = exc
                print(f"Hindi voice attempt {attempt}/3 failed: {exc}")
                if attempt < 3:
                    time.sleep(attempt * 2)
        else:
            raise RuntimeError(f"Hindi voice generation failed: {last_error}") from last_error

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

    async def _generate(self, text: str, output_path: str):
        communicate = edge_tts.Communicate(text, VOICE_NAME)
        await communicate.save(output_path)
