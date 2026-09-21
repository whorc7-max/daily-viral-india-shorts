# Daily Viral India Shorts

Free GitHub Actions automation for two original Hindi YouTube Shorts per day.

Each run:

1. Reads current India trend leads from Google Trends.
2. Uses Gemini to write one original Hindi Short.
3. Downloads optional stock images from Pexels.
4. Generates a natural Hindi voiceover with Edge TTS.
5. Selects CC0 background music from Openverse and mixes it below the voice.
6. Renders a 45-60 second, 9:16 video with synchronized Hindi captions.
7. Uploads the MP4 to YouTube using the official YouTube Data API OAuth flow.

The schedule runs twice daily at 08:44 and 16:47 UTC. Change `.github/workflows/schedule.yml` if you want different times.

## GitHub Secrets

Add these under **Settings -> Secrets and variables -> Actions**:

- `GEMINI_API_KEY`: Google AI Studio key used only for script generation.
- `YT_CLIENT_ID`: Google Cloud OAuth desktop-app client ID.
- `YT_CLIENT_SECRET`: Google Cloud OAuth desktop-app client secret.
- `YT_REFRESH_TOKEN`: YouTube OAuth refresh token for the channel.
- `PEXELS_API_KEY`: optional free Pexels key for stock images. If omitted, the renderer uses generated gradient backgrounds.

Voice uses the free `hi-IN-MadhurNeural` Edge TTS voice by default. Set the optional `TTS_VOICE` repository variable if you prefer another Edge voice.

Optional repository variables:

- `GEMINI_MODEL`: defaults to `gemini-2.5-flash`.
- `YT_PRIVACY_STATUS`: defaults to `public`; use `unlisted` for testing.

## Important

- Do not commit API keys, OAuth tokens, or passwords.
- Use only original commentary and properly licensed stock images.
- Review YouTube's policies for repetitive or AI-assisted content before enabling public uploads.
- GitHub Actions and API providers have quotas and rate limits.
