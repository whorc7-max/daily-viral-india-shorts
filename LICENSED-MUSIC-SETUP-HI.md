# Licensed Song Setup (Hindi)

Automation can select a song by topic only when you provide a direct audio-file URL that the rights-holder authorizes for use in YouTube videos. It does not download from Y2mate or extract audio from a video page.

1. Get a direct HTTPS audio download link from the rights-holder or an authorized music host. Confirm the permission covers adding the song to videos and uploading them to YouTube.
2. In the GitHub repository, open **Settings -> Secrets and variables -> Actions -> New repository secret**.
3. Set the secret name to `LICENSED_MUSIC_CATALOG_JSON`.
4. Use this JSON format and replace the example values:

```json
{"tracks":[{"title":"Licensed rain song","direct_url":"https://authorized-host.example/audio/rain-song.mp3","tags":["rain","monsoon","romantic"],"rights_holder":"Rights-holder name","authorized_for_youtube":true}]}
```

5. Add one object per authorized song. Put matching topic words in `tags`, such as `rain`, `cricket`, `comedy`, or `romantic`.
6. Keep the permission letter/private URL out of the public repository. The automation does not log the direct URL or include it in the source record.

The best matching authorized song is selected first. If no authorized song matches or its download fails, the automation searches free CC0 music; if that also fails, it renders without background music. The secret must contain a direct audio file, not a Y2mate page, YouTube page, or playlist URL.
