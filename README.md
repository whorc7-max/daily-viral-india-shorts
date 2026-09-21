# Daily Viral India Shorts

Free GitHub Actions automation for two original Hindi YouTube Shorts per day.

Each run:

1. Reads current India trend leads from Google Trends.
2. Uses Gemini to write one original Hindi Short.
3. Creates an ordered visual scene plan matching the narration beats.
4. Downloads topic-matched licensed images per scene from Pexels/Openverse.
5. Generates a natural Hindi voiceover with Edge TTS.
6. Selects CC0 background music from Openverse and mixes it below the voice.
7. Renders a 45-60 second, 9:16 video with synchronized Hindi captions and changing visuals.
8. Uploads the MP4 to YouTube using the official YouTube Data API OAuth flow.

Reliability protections:

- Gemini failures fall back to a safe trend-based Hindi script.
- Pexels and Openverse failures fall back per scene, with generated backgrounds in the editor.
- Missing CC0 music falls back to generated ambient audio.
- Network downloads and Hindi voice generation retry automatically.
- A credential health check reports when YouTube authorization needs one-time reauthorization.
- A monthly keepalive commit prevents GitHub's inactivity suspension from stopping schedules.

The schedule runs twice daily at 08:44 and 16:47 UTC. Change `.github/workflows/schedule.yml` if you want different times.

## GitHub Secrets

Add these under **Settings -> Secrets and variables -> Actions**:

- `GEMINI_API_KEY`: Google AI Studio key used for script generation; optional because a safe fallback exists.
- `FIREBASE_REFRESH_TOKEN`: optional Firebase Auth refresh token for loading the current key rotation set from the private AI Studio vault.
- `YT_CLIENT_ID`: Google Cloud OAuth desktop-app client ID.
- `YT_CLIENT_SECRET`: Google Cloud OAuth desktop-app client secret.
- `YT_REFRESH_TOKEN`: YouTube OAuth refresh token for the channel.
- `PEXELS_API_KEY`: optional free Pexels key for stock images. If omitted, the workflow uses free Openverse CC0 images.

Voice uses the free `hi-IN-MadhurNeural` Edge TTS voice by default. Set the optional `TTS_VOICE` repository variable if you prefer another Edge voice.

Optional repository variables:

- `GEMINI_MODEL`: defaults to `gemini-2.5-flash`.
- `YT_PRIVACY_STATUS`: defaults to `public`; use `unlisted` for testing.

## Important

- Do not commit API keys, OAuth tokens, or passwords.
- Use only original commentary and properly licensed stock images.
- Review YouTube's policies for repetitive or AI-assisted content before enabling public uploads.
- GitHub Actions and API providers have quotas and rate limits.
- No automation can bypass provider quotas or revoked credentials. If Google revokes the YouTube OAuth grant,
  reauthorize once and replace `YT_REFRESH_TOKEN` in GitHub Secrets.
- Move the Google OAuth consent screen to Production to avoid Testing-mode refresh-token expiry.
- Set Google Cloud budget alerts before enabling paid Gemini usage; billing is intentionally not enabled by code.
- The Firebase vault bridge never prints Gemini or Firebase token values; if the vault is unavailable, the workflow falls back to `GEMINI_API_KEY`.
