import unittest
from unittest.mock import AsyncMock, patch

from src import voice_generator


class VoiceGeneratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_edge_tts_receives_the_configured_speaking_rate(self):
        with patch("src.voice_generator.edge_tts.Communicate") as communicate:
            communicate.return_value.save = AsyncMock()
            await voice_generator.VoiceGenerator()._generate("Hindi script", "voice.mp3")

        communicate.assert_called_once_with(
            "Hindi script",
            voice_generator.VOICE_NAME,
            rate=voice_generator.VOICE_RATE,
        )
        communicate.return_value.save.assert_awaited_once_with("voice.mp3")


if __name__ == "__main__":
    unittest.main()
