# Daily Viral India Shorts

Free GitHub Actions automation for two original Hindi YouTube Shorts per day.

Each run:

1. Searches India YouTube videos published in the previous two hours across funny/comedy, emotional stories, surprising moments, viral incidents, sports, gaming, movies, music, celebrity/news, and meme trends; ranks candidates with at least 1,000 views by average views per hour since upload. If no candidate qualifies, it falls back to Google Trends.
2. Uses Gemini to write one original Hindi Short.
3. Creates an ordered visual scene plan matching the narration beats.
4. Downloads topic-matched licensed images per scene from Pexels/Openverse.
5. Generates a Hindi voiceover with the configured TTS backend (Chatterbox, ElevenLabs, or Edge TTS).
6. First checks an optional private catalog of rights-holder-authorized tracks and chooses one by topic tags. If no authorized track matches, searches Openverse for a free CC0 track matched to the topic mood. The selected track's title, source, and rights status are saved as `music_source.json`.
7. Adds CC0 ambience matched to each visual scene, with an offline-generated sound bed if no licensed clip is available.
8. Renders a 9:16 video with changing visuals, Hindi narration, continuous music, and scene-changing ambience.
   The renderer adds no text or graphic overlays, including channel branding, titles, captions,
   subtitles, watermarks, or progress indicators.
9. Uploads the MP4 to YouTube using the official YouTube Data API OAuth flow.

Reliability protections:

- Gemini failures fall back to a safe trend-based Hindi script.
- Pexels and Openverse failures fall back per scene, with generated backgrounds in the editor.
- If no suitable CC0 music is available, the Short renders without background music rather than inserting an unrelated tone or unlicensed song.
- Only direct HTTPS audio-file URLs from `LICENSED_MUSIC_CATALOG_JSON` are accepted for authorized tracks. Y2mate and other downloader-page URLs are not used; if a catalog track cannot be fetched, the pipeline falls back to CC0 music.
- Missing CC0 scene sounds fall back to generated ambience tailored to the scene category.
- Network downloads and Hindi voice generation retry automatically.
- A credential health check reports when YouTube authorization needs one-time reauthorization.
- A monthly keepalive commit prevents GitHub's inactivity suspension from stopping schedules.

The schedule runs twice daily at 08:44 and 16:47 UTC. The YouTube search window is the two hours before each run; this does not schedule a run every two hours. Change `.github/workflows/schedule.yml` if you want different times or upload frequency.

## GitHub Secrets

Add these under **Settings -> Secrets and variables -> Actions**:

- `GEMINI_API_KEY`: Google AI Studio key used for script generation; optional because a safe fallback exists.
- `YOUTUBE_API_KEY`: optional Google API key with YouTube Data API v3 enabled. This is needed to search recent YouTube video topics; if unset or no qualifying video is found, the workflow falls back to Google Trends.
- `FIREBASE_REFRESH_TOKEN`: optional Firebase Auth refresh token for loading the current key rotation set from the private AI Studio vault.
- `YT_CLIENT_ID`: Google Cloud OAuth desktop-app client ID.
- `YT_CLIENT_SECRET`: Google Cloud OAuth desktop-app client secret.
- `YT_REFRESH_TOKEN`: YouTube OAuth refresh token for the channel.
- `PEXELS_API_KEY`: optional free Pexels key for stock images. If omitted, the workflow uses free Openverse CC0 images.
- `LICENSED_MUSIC_CATALOG_JSON`: optional GitHub Actions Secret with direct audio URLs that you are authorized to use in YouTube videos. Add only tracks with rights-holder permission covering video use and upload; the pipeline never prints the URL or stores it in `music_source.json`.
- `ELEVENLABS_API_KEY`: optional. When set, the Hindi voiceover uses the configured ElevenLabs voice. Add it only after confirming your account/API plan can access that shared voice; API errors stop the run rather than silently using a different voice.
- `TTS_REFERENCE_AUDIO_BASE64`: optional private voice recording encoded as Base64. The workflow decodes it into the runner's temporary directory and does not include it in artifacts.

Example value for `LICENSED_MUSIC_CATALOG_JSON`:

```json
{"tracks":[{"title":"Licensed rain song","direct_url":"https://authorized-host.example/audio/rain-song.mp3","tags":["rain","monsoon","romantic"],"rights_holder":"Rights-holder name","authorized_for_youtube":true}]}
```

Use a direct HTTPS audio download URL from the authorized rights-holder/source, not a YouTube page or a downloader site. `tags` are matched against the Hindi Short's topic/title and visual keywords. Keep the permission document privately; do not commit it or the song file to this public repository.

Hindi setup steps are in `LICENSED-MUSIC-SETUP-HI.md`.

Voice uses Chatterbox with your reference audio when `TTS_REFERENCE_AUDIO_PATH` is available in `auto` mode; otherwise it uses ElevenLabs when configured, then Edge TTS. Never paste API keys into chat or commit them.

Optional repository variables:

- `GEMINI_MODEL`: defaults to `gemini-2.5-flash`.
- `ELEVENLABS_VOICE_ID`: defaults to `2cdvnKJ5TZi631y5PN1s`.
- `ELEVENLABS_MODEL`: defaults to `eleven_multilingual_v2`.
- `TTS_VOICE`: Edge TTS fallback voice; defaults to `hi-IN-MadhurNeural`.
- `TTS_BACKEND`: optional `chatterbox`, `elevenlabs`, or `edge`; defaults to `auto` (reference audio, then ElevenLabs key, then Edge TTS).
- `TTS_REFERENCE_AUDIO_PATH`: optional path to a private reference-audio file available to the runner. Never place a voice recording in a public repository.
- `CHATTERBOX_DEVICE`: optional `auto`, `cpu`, `cuda`, or `mps`; defaults to automatic selection.
- `YT_PRIVACY_STATUS`: defaults to `public`; use `unlisted` for testing.

### Use your own Hindi voice locally

The optional Chatterbox Multilingual V3 backend supports zero-shot Hindi voice cloning from a reference recording and runs without a vendor API key. It uses the MIT-licensed `chatterbox-tts` package; generated speech is watermarked by the model. A reference clip of at least 10 seconds is recommended by the model provider. The workflow installs this larger dependency only when `TTS_BACKEND=chatterbox` or `TTS_REFERENCE_AUDIO_PATH` is set, and caches downloaded model weights.

To use it in scheduled GitHub Actions without committing audio, set the repository variable `TTS_BACKEND` to `chatterbox` and create the Actions Secret `TTS_REFERENCE_AUDIO_BASE64` with the contents of `outputs/my-voice-actions-secret.txt`. This prepared payload is below GitHub's 48 KB secret limit. The workflow decodes it into the runner's temporary directory; the secret is not printed or included in artifacts. Alternatively, set `TTS_REFERENCE_AUDIO_PATH` to an audio file already available privately on the runner. Do not commit personal voice audio to a public repository. CPU inference can be slower than Edge TTS, and the first run downloads model weights. The original upload is not bundled with this code; the Actions runner cannot read files from this workspace.

Manual runs can choose `public`, `unlisted`, or `private` in the workflow input. Scheduled runs use `YT_PRIVACY_STATUS`, defaulting to `public`.

## AI Studio Control Center GitHub access

The scheduled workflow can run without a personal access token. The AI Studio Control Center needs its own fine-grained GitHub token to start a manual run. For this repository, grant the token **Actions: Read and write** to dispatch workflows and **Secrets: Read and write** to update Actions secrets. Limit repository access to `daily-viral-india-shorts`. Actions read-only is not enough to dispatch a workflow; changing this workflow's `permissions` does not upgrade the app token. Never paste the token into chat or commit it.

Step-by-step Hindi instructions are in `CONTROL-CENTER-PAT-HINDI.md`.

## Important

- Do not commit API keys, OAuth tokens, or passwords.
- Use only original commentary and properly licensed stock images.
- The automation does not copy songs from trending videos. Commercial songs such as "Tip Tip Barsa Pani" are used only if you provide an authorized direct audio source and the appropriate rights-holder permission; otherwise the pipeline uses CC0 mood-matched music.
- CC0 music search uses Openverse and requires no paid music API key. Availability and mood relevance depend on its catalog; `music_source.json` is included with the rendered-video artifact when a track is found.
- Review YouTube's policies for repetitive or AI-assisted content before enabling public uploads.
- GitHub Actions and API providers have quotas and rate limits.
- No automation can bypass provider quotas or revoked credentials. If Google revokes the YouTube OAuth grant,
  reauthorize once and replace `YT_REFRESH_TOKEN` in GitHub Secrets.
- Move the Google OAuth consent screen to Production to avoid Testing-mode refresh-token expiry.
- Set Google Cloud budget alerts before enabling paid Gemini usage; billing is intentionally not enabled by code.
- The Firebase vault bridge never prints Gemini or Firebase token values; if the vault is unavailable, the workflow falls back to `GEMINI_API_KEY`.
